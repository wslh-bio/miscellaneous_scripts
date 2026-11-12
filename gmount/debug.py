# debug.py
from pathlib import Path
from typing import Dict
from utils import COLORS


class DebugPrinter:
    """Formats and prints copy-pasteable mount commands using backend builders."""

    def __init__(self, backends: Dict[str, object], user_vars: Dict[str, str]):
        self.backends = backends
        self.user_vars = user_vars

    def print_mounts(self, config_data: Dict) -> int:
        """
        Iterate through configured mounts and print the exact shell commands
        needed to mount them manually.

        Returns:
            int: Number of mount commands generated
        """
        command_count = 0
        mounts_config = config_data.get('mounts', {})

        print(f"\n{COLORS['cyan']}=== Debug Mode: Manual Mount Commands ==={COLORS['reset']}\n")

        for backend_name, mounts in mounts_config.items():
            backend = self.backends.get(backend_name)
            if not backend:
                print(f"{COLORS['yellow']}# Unsupported backend: {backend_name}{COLORS['reset']}\n")
                continue

            for mount_cfg in mounts:
                comment = mount_cfg.get('comment', f"{backend_name} mount")
                local_path = Path(mount_cfg['local'])
                print(f"{COLORS['green']}# [{backend_name.upper()}] {comment}{COLORS['reset']}")

                if backend_name == 'gvfs':
                    cmd_str = backend.build_mount_command(mount_cfg)
                    hostname = mount_cfg['host']
                    share_root = mount_cfg['share'].strip('/').split('/')[0]
                    server, port = hostname.split(':', 1) if ':' in hostname else (hostname, '445')
                    expected_gvfs_path = backend.get_expected_mount_point(server, port, share_root)

                    print(cmd_str)
                    print(f"mkdir -p {local_path.parent.as_posix()} && ln -sfn {expected_gvfs_path.as_posix()} {local_path.as_posix()}\n")
                    command_count += 1

                elif backend_name == 's3':
                    cmd_list = backend.build_mount_command(mount_cfg)
                    print(f"mkdir -p {local_path.as_posix()}")
                    print(f"{' '.join(cmd_list)}\n")
                    command_count += 1

                elif backend_name == 'cifs':
                    cmd_list = backend.build_mount_command(
                        mount_cfg,
                        user_vars=self.user_vars,
                        debug=True
                    )
                    print(f"mkdir -p {local_path.as_posix()}")
                    print(f"{' '.join(cmd_list)}\n")
                    command_count += 1

        return command_count

