# mount_manager.py


import json
import os
import shutil
from pathlib import Path
from typing import Dict, Tuple, Optional

from gvfs_backend import GVFSBackend
from rclone_backend import RcloneBackend
from utils import log, warning, error
from cifs_backend import CIFSBackend

# Backend type constants
BACKEND_GVFS = "gvfs"
BACKEND_S3   = "s3"
BACKEND_CIFS = "cifs"

class MountManager:
    def __init__(self, config_path: str, pass_manager):
        self.config_path = config_path
        self.config = {}
        self.pass_manager = pass_manager
        self.user_id = os.getuid()
        self.user_gid = os.getgid()
        self.backends = {
            BACKEND_GVFS: GVFSBackend(self.user_id),
            BACKEND_S3: RcloneBackend(),
            BACKEND_CIFS: CIFSBackend()
        }


    def load_config(self, user_vars: Dict[str, str]) -> None:
        """Load mount configuration from JSON file and expand variables."""
        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)

            # Replace placeholders in mount configurations
            for backend, mounts in self.config.get('mounts', {}).items():
                for mount in mounts:
                    for key in ['host', 'share', 'local', 'options', 'config', 'server']:
                        if key in mount:
                            mount[key] = mount[key].replace("@USERNAME", user_vars['user'])
                            mount[key] = mount[key].replace("@FS_UID", user_vars['u_id'])
                            mount[key] = mount[key].replace("@FS_GID", user_vars['g_id'])
                            mount[key] = mount[key].replace("@USER_UID", str(self.user_id))
                            mount[key] = mount[key].replace("@USER_GID", str(self.user_gid))

            # Check if required binaries are installed
                for mount in mounts:
                    if 'backend' in mount:
                        if shutil.which(mount['backend']) is None:
                            raise ValueError(f"{mount['backend']} is not installed")

        except FileNotFoundError:
            raise ValueError(f"Configuration file '{self.config_path}' not found")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {str(e)}")

    def process_mounts(self, user_vars: Dict[str, str], umount_only: bool = False) -> Tuple[int, int]:
        """Process all mounts in configuration."""
        success_count = 0
        failure_count = 0

        for backend, mounts in self.config.get('mounts', {}).items():
            if backend not in self.backends:
                warning(f"Unsupported backend: {backend}")
                continue

            for config in mounts:
                local_path = Path(config['local'])
                backend_instance = self.backends[backend]
                domain = config.get('domain')

                if umount_only:
                    # Unmount operation
                    if backend == BACKEND_GVFS:
                        if backend_instance.umount(config['host'], config['share'].strip('/'), local_path):
                            success_count += 1
                        else:
                            failure_count += 1

                    elif backend == BACKEND_S3:
                        if backend_instance.umount(local_path, config['remote']):
                            success_count += 1
                        else:
                            failure_count += 1

                    elif backend == BACKEND_CIFS:
                        if umount_only:
                            # Unmount operation
                            if backend_instance.umount(local_path, self.pass_manager.password):
                                success_count += 1
                            else:
                                failure_count += 1

                else:
                    # Mount operation
                    if backend == BACKEND_GVFS:
                        is_mounted, mount_point = backend_instance.is_mounted(config['host'], config['share'].strip('/'))
                        if is_mounted:
                            log(f"{config['host']}/{config['share']} is already mounted")

                            # make sure symlink is active/correct
                            if mount_point and backend_instance.establish_symlink(mount_point, local_path):
                                success_count += 1
                            else:
                                failure_count += 1
                        else:
                            if backend_instance.mount(config, user_vars['user'], self.pass_manager.password):
                                success_count += 1
                            else:
                                failure_count += 1

                    elif backend == BACKEND_S3:
                        if backend_instance.is_mounted(local_path):
                            log(f"{config['remote']} is already mounted")
                        else:
                            # ameke sure mount point exists
                            if backend_instance.establish_mount_point(local_path, config['remote']):
                                success_count += 1
                            else:
                                failure_count += 1
                            # mount the bucket
                            if backend_instance.mount(config):
                                success_count += 1
                            else:
                                failure_count += 1

                    elif backend == BACKEND_CIFS:
                            if backend_instance.is_mounted(local_path):
                                log(f"{config['host']}/{config['share']} is already mounted at {local_path}")
                                success_count += 1
                            else:
                                # Check if  mount point exists
                                if backend_instance.establish_mount_point(local_path):
                                    # Mount the share
                                    if backend_instance.mount(config, self.pass_manager.password, user_vars):
                                        success_count += 1
                                    else:
                                        failure_count += 1
                                else:
                                    failure_count += 1

        return success_count, failure_count
