import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple
import os
import time
from utils import log, log_ok, warning, error, notice
import tempfile

class CIFSBackend:
    """Backend for mounting CIFS (SMB) shares using sudo mount.cifs."""

    def __init__(self):
        # Check if required commands are available
        self._check_dependencies()

    def _check_dependencies(self) -> None:
        """Verify that required system commands are available."""
        dependencies = ['sudo', 'mount.cifs', 'umount']
        missing = []

        for cmd in dependencies:
            try:
                subprocess.run(['which', cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            except subprocess.CalledProcessError:
                missing.append(cmd)

        if missing:
            warning(f"Missing required commands for CIFS mounting: {', '.join(missing)}")

    def is_mounted(self, local_path: Path) -> bool:
        """
        Check if a path is already mounted.

        Args:
            local_path: The local mount point to check

        Returns:
            bool: True if the path is mounted, False otherwise
        """
        try:
            mount_output = subprocess.check_output(['mount']).decode('utf-8')
            mount_point_str = local_path.as_posix()
            # Fix to check for exact match on the mount instead of the substring match originally being done.
            # For example, /mnt/slh should not match /mnt/slhfile but that's what was happening.
            # Mount output format: "//server/share on /mount/point type cifs (options)"
            # check for " on {path} type " string or ending with " on {path}" for an exact match instead.
            for line in mount_output.splitlines():
                if f" on {mount_point_str} type " in line or line.endswith(f" on {mount_point_str}"):
                    return True
            return False
        except subprocess.CalledProcessError:
            warning("Failed to get mount information from mount command")
            return False

    def establish_mount_point(self, mount_path: Path) -> bool:
        """
        Ensure a mount point directory exists, creating it if necessary.

        Args:
            mount_path: Path where the filesystem will be mounted

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check if mount point exists
            if mount_path.exists():
                if self.is_mounted(mount_path):
                    # If already mounted, don't touch it
                    log(f"Mount point {mount_path} is already in use")
                    return False

                # Remove empty directory if exists
                elif mount_path.is_dir() and not any(mount_path.iterdir()):
                    mount_path.rmdir()
                else:
                    warning(f"Cannot create mount point: path exists and is not empty: {mount_path}")
                    return False

            # Create parent directories if needed
            mount_path.parent.mkdir(parents=True, exist_ok=True)

            # Create the mount point directory
            mount_path.mkdir(mode=0o755, parents=False, exist_ok=False)

            log_ok(f"Created mount point: {mount_path}")
            return True

        except OSError as e:
            warning(f"Failed to create mount point (leftover directory/symlink?): {e}")
            return False


    def mount(self, config: Dict[str, str], password: Optional[str] = None, user_vars: Dict[str, str] = {}) -> bool:
        """
        Mount a CIFS share using sudo mount.cifs.

        Args:
            config: Mount configuration dictionary with required keys:
                - host: Hostname or IP of the CIFS server
                - share: Share name to mount
                - local: Local path to mount point
                - options: Additional mount options (optional)
            password: Password for authentication (if needed)

        Returns:
            bool: True if successful, False otherwise
        """
        # Validate required configuration
        if not config.get('host') or not config.get('share') or not config.get('local'):
            error("Missing required CIFS configuration: host, share, and local path must be specified", exit_code=None)
            return False

        local_path = Path(config['local'])
        host = config['host']
        share = config['share']
        domain = config.get('domain')

        # Parse server and port from host
        server = host
        port = None
        if ':' in host:
            server, port = host.split(':', 1)

        # Create proper UNC path
        unc_path = f"//{server}{share}"
        log(f"Mounting CIFS share {unc_path} to {local_path}")

        # Prepare mount point
        if not local_path.exists():
            if not self.establish_mount_point(local_path):
                error(f"Failed to create mount point at {local_path}", exit_code=None)
                return False

        # Create secure temporary password file
        try:
            # Create temp file in /run/user/$UID/
            temp_file = tempfile.NamedTemporaryFile(
                dir=f"/run/user/{os.getuid()}",
                prefix='cifs.pass.',
                mode='w',
                delete=False  # We'll handle deletion manually
            )

            # Write credentials to file
            if password:
                temp_file.write(f"password={password}\n")
                temp_file.write(f"username={user_vars['user']}\n")
                temp_file.write(f"domain={domain}\n")
            temp_file.close()  # Close but don't delete yet

            # Prepare mount options with credentials file
            mount_options = f"credentials={temp_file.name}"

            # Add domain if specified
            if 'domain' in config:
                mount_options += f",domain={config['domain']}"

            # Add additional options if specified
            if 'options' in config:
                mount_options += f",{config['options']}"

            # Add port to options if specified
            if port:
                mount_options = f"port={port},{mount_options}" if mount_options else f"port={port}"

            # Build mount command
            cmd = [
                '/bin/sudo', 'mount', '-t', 'cifs',
                unc_path,  # Use the properly formatted UNC path
                local_path.as_posix(),
            ]

            # Add options if any
            if mount_options:
                cmd.extend(['-o', mount_options])

            log(f"Executing mount command: {' '.join(cmd)}")

            try:
                # Execute mount command
                process = subprocess.run(
                    cmd,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True  # Use text mode for easier output handling
                )

                # Check if mount was successful using polling instead of sleep
                max_retries = 5
                retry_interval = 0.5

                for attempt in range(max_retries):
                    if self.is_mounted(local_path):
                        log_ok(f"Successfully mounted {unc_path} to {local_path}")
                        return True

                    if attempt < max_retries - 1:
                        time.sleep(retry_interval)

                warning(f"Mount command completed but {local_path} is not mounted after {max_retries} verification attempts")
                return False

            except subprocess.CalledProcessError as e:
                error_output = e.stderr.strip() if e.stderr else "Unknown error"
                error_code = e.returncode

                # Provide more specific error messages based on common mount.cifs error codes
                if error_code == 32:
                    warning(f"Failed to mount {unc_path}: Authentication failure (error code {error_code})")
                elif error_code == 5:
                    warning(f"Failed to mount {unc_path}: Permission denied (error code {error_code})")
                elif error_code == 115:
                    warning(f"Failed to mount {unc_path}: Operation in progress, try again later (error code {error_code})")
                else:
                    warning(f"Failed to mount {unc_path}: {error_output} (error code {error_code})")

                return False
            except Exception as e:
                error(f"Unexpected error mounting {unc_path}: {str(e)}", exit_code=None)
                return False
            finally:
                # Clean up temporary password file if it exists
                if os.path.exists(temp_file.name):
                    os.unlink(temp_file.name)

        except Exception as e:
            error(f"Failed to create temporary password file: {str(e)}", exit_code=None)
            return False



    def umount(self, local_path: Path, password: Optional[str] = None) -> bool:
        """
        Unmount a CIFS share.

        Args:
            local_path: Path where the share is mounted

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_mounted(local_path):
            notice(f"{local_path} is not mounted")
            return True

        log(f"Unmounting {local_path}")

        try:
            # Execute unmount command with sudo
            subprocess.run(
                ['/bin/sudo', 'umount', local_path.as_posix()],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            log_ok(f"Successfully unmounted {local_path}")

            # Wait briefly to ensure the unmount is complete
            time.sleep(1)

            return True
        except subprocess.CalledProcessError as e:
            error_output = e.stderr.decode('utf-8').strip()
            warning(f"Failed to unmount {local_path}: {error_output}")

            # Suggest possible solutions for common issues
            if "device is busy" in error_output:
                notice("The mount point may be in use. Try closing all programs using it and try again.")

            return False

    def is_mount_ready(self, mount_point: Path, timeout: int = 10) -> bool:
        """
        Check if a mounted filesystem is ready for use.

        Args:
            mount_point: Path to the mount point
            timeout: Maximum time to wait for the mount to be ready, in seconds

        Returns:
            bool: True if the mount is ready, False otherwise
        """
        if not mount_point.exists() or not self.is_mounted(mount_point):
            return False

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Try listing directory contents
                list(mount_point.iterdir())
                return True
            except (OSError, FileNotFoundError, PermissionError):
                time.sleep(0.5)

        warning(f"Mount point {mount_point} exists but is not responsive")
        return False