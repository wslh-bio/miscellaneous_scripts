# utils.py
import os
import signal
import subprocess
import sys
from typing import Dict, Optional

# ANSI color codes
COLORS = {
    'lightgreen': '\033[1;32m',
    'silver': '\033[90m',
    'cyan': '\033[96m',
    'green': '\033[0;32m',
    'yellow': '\033[93m',
    'red': '\033[91m',
    'reset': '\033[0m',
    'magenta': '\033[95m',
    'light_cyan': '\033[96m'
}


def log(message: str) -> None:
    """
    Log an info message with cyan color.
    
    Args:
        message: The message to log
    """
    print(f"{COLORS['cyan']}Info: {COLORS['silver']}{message}{COLORS['reset']}")

def notice(message: str) -> None:
    """
    Log a notice message with magenta color.
    
    Args:
        message: The message to log
    """
    print(f"{COLORS['magenta']}Notice: {COLORS['light_cyan']}{message}{COLORS['reset']}")
    
def log_ok(message: str) -> None:
    """
    Log a success message with green color.
    
    Args:
        message: The message to log
    """
    print(f"{COLORS['green']}OK: {COLORS['lightgreen']}{message}{COLORS['reset']}")


def warning(message: str) -> None:
    """
    Log a warning message with yellow color.
    
    Args:
        message: The warning message
    """
    print(f"{COLORS['yellow']}Warning: {message}{COLORS['reset']}")


def error(message: str, exit_code: Optional[int] = 1) -> None:
    """
    Log an error message with red color and optionally exit.
    
    Args:
        message: The error message
        exit_code: If not None, exit with this code; otherwise just log
    """
    print(f"{COLORS['red']}Error: {message}{COLORS['reset']}")
    if exit_code is not None:
        sys.exit(exit_code)


def break_handler(sig, frame) -> None:
    """
    Handle keyboard interrupts (CTRL+C) by cleaning up before exiting.
    
    Args:
        sig: Signal number
        frame: Current stack frame
    """
    print("\n")  # Print a newline for aesthetics after ^C
    warning("Keyboard interrupt detected - exiting")
    sys.exit(1)


def get_user_ids() -> Dict[str, str]:
    """
    Retrieve user ID and group ID using system commands.
    
    Returns:
        Dictionary with 'u_id' and 'g_id' keys
    """
    try:
        uid = subprocess.check_output(['id', '-u']).decode('utf-8').strip()
        gid = subprocess.check_output(['id', '-g']).decode('utf-8').strip()
        return {'u_id': uid, 'g_id': gid}
    except subprocess.CalledProcessError as e:
        warning(f"Failed to retrieve user/group IDs: {e}")
        return {'u_id': str(os.getuid()), 'g_id': str(os.getgid())}