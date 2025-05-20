# backends/rclone_backend.py
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple
import time
from utils import log, log_ok, warning, notice

class RcloneBackend:
    def __init__(self):
        pass

    def is_mounted(self, local_path: Path) -> bool:
        """Check if a path is mounted using the `mount` command."""
        try:
            mount_output = subprocess.check_output(['mount']).decode('utf-8')
            return any(local_path.as_posix() in line for line in mount_output.splitlines())
        except subprocess.CalledProcessError:
            warning("Failed to get mount information from mount command")
            return False

        
    def bucket_from_remote_path(self, remote_path: str) -> Tuple[bool, str]:
        """
        Extract bucket name from an rclone remote path.
        
        Args:
            remote_path: String in the format "remote_name:/path/to/bucket" or "remote_name:bucket"
        
        Returns:
            The bucket name or a descriptive error message if the format is invalid
        """
        if not remote_path or ':' not in remote_path:
            return False, "invalid bucket format. should be like rclone_id:/my-bucket-9376"
        
        parts = remote_path.split(':', 1)  # Split only on first colon
        if len(parts) != 2:
            return False, "invalid bucket format. should be like rclone_id:/my-bucket-9376"
        
        remote_name, path = parts
        if not remote_name:
            return False, "missing remote name. should be like rclone_id:/my-bucket-9376"
        
        # Strip leading and trailing slashes from path part
        bucket = path.strip('/')
        
        # If path has multiple segments, take the first one as bucket name
        if '/' in bucket:
            bucket = bucket.split('/', 1)[0]
        
        return True, bucket


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


    
    def establish_mount_point(self, mount_path: Path, remote_path: str) -> bool:
        """
        Ensure a mount point directory exists, creating it if necessary.
        
        Args:
            mount_path: Path where the filesystem will be mounted
            device_path: Path to the device/block device being mounted
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check if mount point exists
            if mount_path.exists():
                if self.is_mounted(mount_path):
                    # Use the existing umount method
                    self.umount(mount_path, remote_path)
                
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
            warning(f"Failed to create mount point: {e}")
            return False
        
    
    def mount(self, config: Dict[str, str]) -> bool:
        """Mount an S3 bucket using Rclone."""
        local_path = Path(config['local'])
        rclone_config = config['config']
        remote_path = config.get('remote', '')
        log(f"Mounting S3 bucket ({remote_path} -> {local_path})")
        # Construct the rclone mount command
        #   rclone mount --config="/home/bladertm/.config/rclone/rclone.conf"  acloud: ~/mnt/my-bucket-9376 --vfs-cache-mode full
        #   bucket="my-bucket-9376"; test ! -d $HOME/mnt/${bucket} && mkdir $HOME/mnt/${bucket}; rclone mount --config="$HOME/.config/rclone/rclone.conf"  acloud: $HO --vfs-cache-mode full
        # rclone mount acloud:/ /home/bladertm/mnt/my-bucket-9376   --vfs-cache-mode full
        #
        # rclone mount acloud:/my-bucket-9376 /home/bladertm/mnt/my-bucket-9376   --vfs-cache-mode full
        # sample rclone.conf entry for below:
        #
        # [acloud]  # < bucket my-bucket-9366 is defined in this account
        # type = s3
        # provider = AWS
        # env_auth = true
        # region = us-east-1
        # acl = private
        # server_side_encryption = AES256
        # 
        cmd = [
            'rclone', 'mount',
            '--config', rclone_config,
            remote_path,
            local_path.as_posix(),
            '--vfs-cache-mode',
            'full',
            '--daemon'
        ]
        try:
            subprocess.run(cmd, check=True)
            time.sleep(5)
            if self.is_mount_ready(local_path):
                log_ok(f"Successfully mounted {remote_path} to {local_path}")
            else:                
                notice (f"rclone command for {remote_path} was successful but {local_path} may not yet be active.")            
        except subprocess.CalledProcessError as e:
            warning(f"Failed to mount {remote_path} to {local_path}: {e}")
            return False


    def umount(self, local_path: Path, remote_path: str) -> bool:
        """Unmount an S3 bucket using Rclone."""
        
        status, bucket = self.bucket_from_remote_path (remote_path)
        if not status:
            log(f"Invalid remote path: {remote_path}. ({bucket})")
            return False
        
        if not self.is_mounted(local_path):
            log(f"Bucket {bucket} is not mounted on {local_path}")
            return True

        log(f"Unmounting {bucket}")

        # Construct the rclone umount command
        cmd = [
            'fusermount', '-u',
            local_path.as_posix()
        ]

        try:
            subprocess.run(cmd, check=True)
            log_ok(f"Successfully unmounted {bucket}")
            return True
        except subprocess.CalledProcessError as e:
            warning(f"Failed to unmount {bucket} on {local_path}: {e}")
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
