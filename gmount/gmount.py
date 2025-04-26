#!/usr/bin/env python3

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import getpass
import pexpect

# ANSI color codes
COLORS = {
    'lightgreen': '\033[1;32m',
    'silver': '\033[90m',
    'cyan': '\033[96m',
    'green': '\033[0;32m',
    'yellow': '\033[93m',
    'red': '\033[91m',
    'reset': '\033[0m'
}

# Global variable to store the PassManager instance for signal handlers
global_pass_manager = None


def log(message: str):
    """Log an info message with cyan color."""
    print(f"{COLORS['cyan']}Info: {COLORS['silver']}{message}{COLORS['reset']}")


def log_ok(message: str):
    """Log a success message with green color."""
    print(f"{COLORS['green']}OK: {COLORS['lightgreen']}{message}{COLORS['reset']}")


def warning(message: str):
    """Log a warning message with yellow color."""
    print(f"{COLORS['yellow']}Warning: {message}{COLORS['reset']}")


def error(message: str, exit_code: int = 1):
    """Log an error message with red color and exit."""
    print(f"{COLORS['red']}Error: {message}{COLORS['reset']}")
    sys.exit(exit_code)


def break_handler(sig, frame):
    """Handle keyboard interrupts (CTRL+C) by cleaning up before exiting."""
    print("\n")  # Print a newline for aesthetics after ^C
    warning("Keyboard interrupt detected - exiting")
    sys.exit(1)


class PassManager:
    """Manages authentication credentials for mount operations."""

    def __init__(self):
        """Initialize the PassManager."""
        self.password = None
        self.username = getpass.getuser()

    def get_pass(self) -> Optional[str]:
        """Prompt the user for a password."""
        try:
            self.password = getpass.getpass(f"{COLORS['yellow']}Enter password: {COLORS['reset']}")
            return self.password
        except (EOFError, KeyboardInterrupt):
            error("Password entry cancelled.")
            return None


class MountManager:
    """Manages filesystem mount operations based on a configuration file."""

    def __init__(self, config_path: str, pass_manager: PassManager):
        """Initialize with configuration path and PassManager instance."""
        self.config_path = config_path
        self.config = {}
        self.pass_manager = pass_manager
        self.user_id = os.getuid()
        self.gvfs_base_path = Path(f"/var/run/user/{self.user_id}/gvfs")

    def load_config(self, user_vars: Dict[str, str]) -> None:
        """Load mount configuration from JSON file and expand variables."""
        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)

            # Replace placeholders in mount configurations
            if 'gvfs' in self.config.get('mounts', {}):
                for mount in self.config['mounts']['gvfs']:
                    for key in ['host', 'path', 'local', 'options']:
                        if key in mount:
                            mount[key] = mount[key].replace("@USERNAME", user_vars['user'])
                            mount[key] = mount[key].replace("@FS_UID", user_vars['u_id'])
                            mount[key] = mount[key].replace("@FS_GID", user_vars['g_id'])
        except FileNotFoundError:
            raise ValueError(f"Configuration file '{self.config_path}' not found")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {str(e)}")

    def parse_mount_info(self) -> List[Dict[str, str]]:
        """Parse gio mount -l output to get information about mounted filesystems."""
        try:
            gio_output = subprocess.check_output(['gio', 'mount', '-l']).decode('utf-8')
            mounts = []
            
            # Looking for lines like: "Mount(0): data on localhost -> smb://localhost:4453/data/"
            smb_pattern = re.compile(r'Mount\(\d+\):.+?->\s+smb://([^/]+)(/.*?)?\s*$', re.MULTILINE)
            
            for match in smb_pattern.finditer(gio_output):
                host = match.group(1)
                path = match.group(2) or '/'
                
                # Parse hostname and port
                if ':' in host:
                    hostname, port = host.split(':', 1)
                else:
                    hostname, port = host, '445'  # Default SMB port
                
                # Parse share path (first directory in path)
                share = path.strip('/').split('/')[0] if path.strip('/') else ''
                
                mounts.append({
                    'hostname': hostname.lower(),
                    'port': port,
                    'share': share.lower(),
                    'path': path.lower(),
                    'full_url': f"smb://{host}{path}".lower()
                })
            
            return mounts
        except subprocess.CalledProcessError:
            warning("Failed to get mount information from gio command")
            return []

    def find_gvfs_mount_point(self, hostname: str, port: str, share: str) -> Optional[Path]:
        """Find the GVFS mount point for a given server, port and share."""
        # Pattern for GVFS mount directory: smb-share:port=XXX,server=XXX,share=XXX
        expected_pattern = f"smb-share:port={port},server={hostname.lower()},share={share.lower()}"
        
        try:
            # Check if GVFS base directory exists
            if not self.gvfs_base_path.exists():
                return None
                
            # Look for directories matching our pattern
            for entry in self.gvfs_base_path.iterdir():
                entry_name = entry.name.lower()
                if expected_pattern in entry_name:
                    return entry
                    
            return None
        except (PermissionError, FileNotFoundError) as e:
            warning(f"Error accessing GVFS directory: {e}")
            return None

    def get_expected_mount_point(self, hostname: str, port: str, share: str) -> Path:
        """Get the expected path for a GVFS mount point based on standard pattern."""
        # Return the expected path pattern regardless of whether it exists
        return self.gvfs_base_path / f"smb-share:port={port},server={hostname.lower()},share={share.lower()}"

    def is_mounted(self, host: str, share: str) -> Tuple[bool, Optional[Path]]:
        """
        Check if a share is mounted and return its mount point.
        
        Args:
            host: Hostname with optional port (e.g., 'server:445')
            share: Share name
            
        Returns:
            Tuple of (is_mounted, mount_point_path)
        """
        # Split host and port if needed
        if ':' in host:
            hostname, port = host.split(':', 1)
        else:
            hostname, port = host, '445'
        
        # Check gio mount output first (more reliable indicator of mount status)
        mounts = self.parse_mount_info()
        for mount in mounts:
            if (mount['hostname'] == hostname.lower() and 
                mount['port'] == port and 
                mount['share'] == share.lower()):
                
                # It's definitely mounted according to gio
                # Try to find the actual directory
                mount_point = self.find_gvfs_mount_point(hostname, port, share)
                if mount_point:
                    return True, mount_point
                else:
                    # We know it's mounted but can't find the directory
                    # Return the expected path
                    return True, self.get_expected_mount_point(hostname, port, share)
        
        # If not found in gio, check GVFS directory as a fallback
        mount_point = self.find_gvfs_mount_point(hostname, port, share)
        if mount_point and mount_point.exists():
            return True, mount_point
                
        return False, None

    def establish_symlink (self, target_path: Path, link_path: Path) -> bool:
        """Ensure a symlink exists, creating it if necessary."""
        try:
            # Create parent directory if needed
            link_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Remove existing symlink or empty directory
            if link_path.exists():
                if link_path.is_symlink():
                    link_path.unlink()
                elif link_path.is_dir() and not any(link_path.iterdir()):
                    link_path.rmdir()
                else:
                    warning(f"Cannot create symlink: path exists and is not empty: {link_path}")
                    return False
            
            # Create the symlink
            link_path.symlink_to(target_path, target_is_directory=True)
            log_ok(f"Created/updated symlink: {link_path} -> {target_path}")
            return True
        except OSError as e:
            warning(f"Failed to create symlink: {e}")
            return False

    def mount_gvfs(self, config: Dict[str, str], user_vars: Dict[str, str]) -> bool:
        """Mount a GVFS (GNOME Virtual File System) share."""
        # Extract configuration details
        hostname = config['host']
        share = config['share'].strip('/')
        share_root = share.split('/')[0]  # Get first directory in share path
        username = user_vars.get('user', self.pass_manager.username)
        local_path = Path(config['local'])
        
        # Get port if specified in hostname
        if ':' in hostname:
            server, port = hostname.split(':', 1)
        else:
            server, port = hostname, '445'  # Default SMB port
        
        # Format URL for gio mount command
        gvfs_url = f"smb://{hostname}/{share}"
        
        log(f"Mounting {gvfs_url}")
        
        # Use pexpect to handle interactive prompts
        try:
            child = pexpect.spawn(f'gio mount "{gvfs_url}"')
            
            # Define possible prompts
            prompts = ['Authentication Required', 'User', 'Domain', 'Password:', pexpect.EOF, pexpect.TIMEOUT]
            
            # Handle authentication prompts
            while True:
                i = child.expect(prompts, timeout=15)
                
                if i == 0:  # Authentication Required
                    continue
                elif i == 1:  # User prompt
                    child.sendline(username)
                elif i == 2:  # Domain prompt
                    domain = config.get('domain', '')
                    child.sendline(domain)
                elif i == 3:  # Password prompt
                    password = self.pass_manager.password or ""
                    child.sendline(password)
                elif i == 4:  # EOF - command completed
                    child.close()
                    
                    if child.exitstatus == 0:
                        log_ok(f"Successfully mounted {gvfs_url}")
                        
                        # Give the system a moment to update
                        time.sleep(1)
                        
                        # Check if mount is registered with gio
                        is_mounted, mount_point = self.is_mounted(hostname, share_root)
                        
                        if is_mounted:
                            # Mount exists according to gio
                            if mount_point:
                                # Create symlink to the actual or expected mount point
                                # Regardless of whether we can access it yet (it might be slow to respond)
                                return self.establish_symlink (mount_point, local_path)
                            else:
                                # Fall back to expected path pattern
                                expected_mount = self.get_expected_mount_point(server, port, share_root)
                                log(f"Using expected mount path: {expected_mount}")
                                return self.establish_symlink (expected_mount, local_path)
                        else:
                            # Strange situation: gio reports success but mount is not listed
                            # Try once more with a delay
                            time.sleep(2)
                            is_mounted, mount_point = self.is_mounted(hostname, share_root)
                            
                            if is_mounted and mount_point:
                                return self.establish_symlink (mount_point, local_path)
                            else:
                                # Last resort - use expected path pattern
                                expected_mount = self.get_expected_mount_point(server, port, share_root)
                                log(f"Mount command succeeded but mount not found in gio output. Using expected path: {expected_mount}")
                                return self.establish_symlink (expected_mount, local_path)
                    else:
                        warning(f"Failed to mount {gvfs_url} (check connection/password). Exit status was {child.exitstatus}")
                        return False
                        
                elif i == 5:  # Timeout
                    warning(f"Mount operation timed out for {gvfs_url}")
                    return False
                    
        except Exception as e:
            warning(f"Error during mount operation: {e}")
            return False

    def umount_gvfs(self, hostname: str, share: str, local_path: Path) -> bool:
        """Unmount a GVFS share."""
        # Remove symlink if it exists
        if local_path.is_symlink():
            try:
                local_path.unlink()
                log(f"Removed symlink: {local_path}")
            except OSError as e:
                warning(f"Failed to remove symlink {local_path}: {e}")
        
        # Check if the share is mounted
        is_mounted, _ = self.is_mounted(hostname, share)
        if not is_mounted:
            log(f"Share {hostname}/{share} is not mounted")
            return True
        
        # Unmount the share
        try:
            gvfs_url = f"smb://{hostname}/{share}"
            log(f"Unmounting {gvfs_url}")
            subprocess.run(['gio', 'mount', '--unmount', gvfs_url], check=True)
            log_ok(f"Successfully unmounted {gvfs_url}")
            return True
        except subprocess.CalledProcessError as e:
            warning(f"Failed to unmount {gvfs_url}: {e}")
            return False

    def is_mount_ready(self, mount_point: Path, timeout: int = 10) -> bool:
        """
        Check if a mounted filesystem is ready for use.
        This is separate from creating symlinks - symlinks should be created
        regardless of mount readiness.
        """
        if not mount_point or not mount_point.exists():
            return False
            
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Try listing directory contents
                list(mount_point.iterdir())
                return True
            except (OSError, FileNotFoundError):
                time.sleep(0.5)
                
        warning(f"Mount point {mount_point} exists but is not responsive")
        return False

    def process_mounts(self, user_vars: Dict[str, str], umount_only: bool = False) -> Tuple[int, int]:
        """Process all GVFS mounts in configuration."""
        success_count = 0
        failure_count = 0
        
        if 'gvfs' not in self.config.get('mounts', {}):
            warning("No GVFS mounts configured")
            return 0, 0
        
        for config in self.config['mounts']['gvfs']:
            hostname = config['host']
            share = config['share'].strip('/')
            local_path = Path(config['local'])
            
            # Get first directory in share path
            share_root = share.split('/')[0]
            
            # Check current mount status
            is_mounted, mount_point = self.is_mounted(hostname, share_root)
            
            if umount_only:
                # Unmount operation
                if self.umount_gvfs(hostname, share_root, local_path):
                    success_count += 1
                else:
                    failure_count += 1
            else:
                # Mount operation
                if is_mounted:
                    log(f"{hostname}/{share} is already mounted")
                    
                    # Ensure symlink exists, even if the mount isn't fully ready yet
                    if mount_point and self.establish_symlink (mount_point, local_path):
                        # Optional: Check if mount is ready, but don't fail if it's not
                        if not self.is_mount_ready(mount_point, timeout=3):
                            log(f"Mount exists but is not yet responsive. Symlink created anyway.")
                        success_count += 1
                    else:
                        failure_count += 1
                else:
                    # Mount the share
                    if self.mount_gvfs(config, user_vars):
                        success_count += 1
                    else:
                        failure_count += 1
        
        return success_count, failure_count


def get_user_ids() -> Dict[str, str]:
    """Retrieve user ID and group ID using system commands."""
    try:
        uid = subprocess.check_output(['id', '-u']).decode('utf-8').strip()
        gid = subprocess.check_output(['id', '-g']).decode('utf-8').strip()
        return {'u_id': uid, 'g_id': gid}
    except subprocess.CalledProcessError as e:
        warning(f"Failed to retrieve user/group IDs: {e}")
        return {'u_id': str(os.getuid()), 'g_id': str(os.getgid())}


def main():
    """Main entry point for the script."""
    # Register signal handler for CTRL+C
    signal.signal(signal.SIGINT, break_handler)

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Manage GVFS filesystem mounts')
    parser.add_argument('-c', '--config', default='gmount.json', help='Path to JSON configuration file')
    parser.add_argument('-u', '--umount', action='store_true', help='Unmount instead of mount')
    args = parser.parse_args()

    # Get environment variables for path expansion
    user_vars = {
        'user': os.environ.get('LOGNAME', ''),
        **get_user_ids(),
    }

    # Create a PassManager instance
    global global_pass_manager
    global_pass_manager = PassManager()

    # Get password if needed (only when mounting)
    if not args.umount:
        password = global_pass_manager.get_pass()
        if not password:
            error("No password entered, exiting...")
            return 1

    # Create and configure the MountManager
    manager = MountManager(args.config, global_pass_manager)
    
    try:
        manager.load_config(user_vars=user_vars)
        success_count, failure_count = manager.process_mounts(user_vars, args.umount)
        
        # Report results
        log(f"{success_count} successful operations, {failure_count} failed operations")
        return 0 if success_count > 0 else 1
    except ValueError as e:
        error(f"Configuration error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())