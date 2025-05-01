#!/usr/bin/env python3
# gmount.py
import argparse
import os
import signal
import sys
import getpass
from typing import Optional

from mount_manager import MountManager
from utils import break_handler, get_user_ids, error, log, warning, COLORS


class PassManager:
    """Manages authentication credentials for mount operations."""
    
    def __init__(self):
        """Initialize the PassManager."""
        self.password = None
        self.username = os.getenv('LOGNAME', '')
        
    def get_pass(self) -> Optional[str]:
        """
        Prompt the user for a password.
        
        Returns:
            str or None: The entered password or None if cancelled
        """
        try:
            self.password = getpass.getpass(f"{COLORS['yellow']}Enter password: {COLORS['reset']}")
            return self.password
        except (EOFError, KeyboardInterrupt):
            warning("Password entry cancelled.")
            return None


def main():
    """
    Main entry point for the script.
    
    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    # Register signal handler for CTRL+C
    signal.signal(signal.SIGINT, break_handler)
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Manage filesystem mounts')
    parser.add_argument('-c', '--config', default='gmount.json', 
                        help='Path to JSON configuration file')
    parser.add_argument('-u', '--umount', action='store_true', 
                        help='Unmount instead of mount')
    args = parser.parse_args()
    
    # Get environment variables for path expansion
    user_vars = {
        'user': os.environ.get('LOGNAME', ''),
        **get_user_ids(),
    }
    
    # Create a PassManager instance
    pass_manager = PassManager()
    
    # Get password if needed (only when mounting)
    if not args.umount:
        password = pass_manager.get_pass()
        if not password:
            return 1  # Error already logged in get_pass
    
    # Create and configure the MountManager
    try:
        manager = MountManager(args.config, pass_manager)
        manager.load_config(user_vars=user_vars)
        success_count, failure_count = manager.process_mounts(user_vars, args.umount)
        
        # Report results
        log(f"{success_count} successful operations, {failure_count} failed operations")
        return 0 if success_count > 0 else 1
        
    except ValueError as e:
        error(f"Configuration error: {e}", exit_code=None)
        return 1


if __name__ == '__main__':
    sys.exit(main())