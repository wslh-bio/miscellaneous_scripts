# backends/gvfs_backend.py

import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import time

import pexpect
from utils import log, log_ok, warning

class GVFSBackend:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.gvfs_base_path = Path(f"/var/run/user/{self.user_id}/gvfs")

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

    def establish_symlink(self, target_path: Path, link_path: Path) -> bool:
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

    def mount(self, config: Dict[str, str], username: str, password: Optional[str]) -> bool:
        """Mount a GVFS (GNOME Virtual File System) share."""
        # Extract configuration details
        hostname = config['host']
        share = config['share'].strip('/')
        share_root = share.split('/')[0]  # Get first directory in share path
        local_path = Path(config['local'])

        # Get port if specified in hostname
        if ':' in hostname:
            server, port = hostname.split(':', 1)
        else:
            server, port = hostname, '445'  # Default SMB port

        # Format URL for gio mount command
        gvfs_url = f"smb://{hostname}/{share}"

        log(f"Mounting {gvfs_url} ({config['comment']})")

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
                    child.sendline(password or "")
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
                                return self.establish_symlink(mount_point, local_path)
                            else:
                                # Fall back to expected path pattern
                                expected_mount = self.get_expected_mount_point(server, port, share_root)
                                log(f"Using expected mount path: {expected_mount}")
                                return self.establish_symlink(expected_mount, local_path)
                        else:
                            # Strange situation: gio reports success but mount is not listed
                            # Try once more with a delay
                            time.sleep(2)
                            is_mounted, mount_point = self.is_mounted(hostname, share_root)

                            if is_mounted and mount_point:
                                return self.establish_symlink(mount_point, local_path)
                            else:
                                # Last resort - use expected path pattern
                                expected_mount = self.get_expected_mount_point(server, port, share_root)
                                log(f"Mount command succeeded but mount not found in gio output. Using expected path: {expected_mount}")
                                return self.establish_symlink(expected_mount, local_path)
                    else:
                        warning(f"Failed to mount {gvfs_url} (check connection/password?). Exit status was {child.exitstatus}")
                        return False

                elif i == 5:  # Timeout
                    warning(f"Mount operation timed out for {gvfs_url}")
                    return False

        except Exception as e:
            warning(f"Error during mount operation: {e}")
            return False

    def umount(self, hostname: str, share: str, local_path: Path) -> bool:
        """Unmount a GVFS share."""
        gvfs_url = None
        
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
