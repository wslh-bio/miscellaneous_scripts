#!/usr/bin/env python3
import os
import sys
import hashlib
import argparse
from pathlib import Path
from typing import Dict, Set, Any, Callable
from functools import wraps

# ╔════════════════════════════════════════════════════════════╗
# ║ This script compares SHA1 checksums of files between two   ║░
# ║ directories to identify matching and non-matching files.   ║░
# ╚════════════════════════════════════════════════════════════╝░
#   ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

# ANSI escape sequences for colors
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"
BLUE = "\033[94m"      # Bright blue
MAGENTA = "\033[95m"   # Bright magenta
LIGHT_CYAN = "\033[96m" # Bright cyan
NULL_SHA1_HASH = "da39a3ee5e6b4b0d3255bfef95601890afd80709"  # sha1 hash of a 0-byte/empty file


def exception_handler(func: Callable) -> Callable:
    """
    Decorator to handle exceptions in a generic way.
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"{RED}Error in {func.__name__}: {e}{RESET}")
            sys.exit(1)
    return wrapper


@exception_handler
def calculate_sha1(file_path: Path) -> str:
    """
    Calculate the SHA1 hash of a file using buffered reading.
    
    Args:
        file_path: Path to the file to hash
        
    Returns:
        SHA1 hash as hexadecimal string
    """
    sha1_hash = hashlib.sha1()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha1_hash.update(byte_block)
    return sha1_hash.hexdigest()



@exception_handler
def collect_hashes(directory: Path) -> Dict[str, Set[Path]]:
    """
    Collect SHA1 hashes of all files in the given directory.
    
    Args:
        directory: Directory to scan for files
        
    Returns:
        Dictionary mapping hashes to sets of matching file paths
    """
    hash_dict: Dict[str, Set[Path]] = {}
    
    for file_path in directory.glob("*"):
        if file_path.is_file():
            file_hash = calculate_sha1(file_path)
            if file_hash not in hash_dict:
                hash_dict[file_hash] = set()
            hash_dict[file_hash].add(file_path)
    
    return hash_dict



@exception_handler
def check_empty(hash_value: str) -> str:
    """
    Return the empty indicator string if the hash value is the null SHA-1 hash.

    Args:
        hash_value: The hash value to check

    Returns:
        Empty indicator string if the hash value is the null SHA-1 hash, otherwise an empty string
    """
    return f" {RED}(EMPTY FILE){RESET} " if hash_value == NULL_SHA1_HASH else " "


@exception_handler
def compare_directories(source_hashes: Dict[str, Set[Path]], 
                       dest_hashes: Dict[str, Set[Path]]) -> None:
    """
    Compare hashes between source and destination directories.
    
    Args:
        source_hashes: Dictionary of hashes from source directory
        dest_hashes: Dictionary of hashes from destination directory
    """
    # Find matching hashes
    matching_hashes = set(source_hashes.keys()) & set(dest_hashes.keys())
    
    # Process matching files
    for hash_value in matching_hashes:
        source_files = source_hashes[hash_value]
        dest_files = dest_hashes[hash_value]
        
        for source_file in source_files:
            # indicate if file is 0-byte/empty
            empty_buf = check_empty(hash_value)
            
            print(f"{GREEN}SOURCE MATCH FOUND:{RESET} {BLUE}{source_file.name}{RESET} ({hash_value}) with{empty_buf}destination file(s):")
            for dest_file in dest_files:
                print(f"  {MAGENTA}{dest_file.absolute()}{RESET}")
    
    # Process non-matching files
    non_matching_source = set(source_hashes.keys()) - matching_hashes
    non_matching_dest = set(dest_hashes.keys()) - matching_hashes
    
    # Print source files with no matches
    if non_matching_source:
        print(f"\n{RED}SOURCE FILES WITH NO MATCHES:{RESET}")
        for hash_value in non_matching_source:
            for source_file in source_hashes[hash_value]:
                empty_buf = check_empty(hash_value)
                print(f"  {BLUE}{source_file.name}{RESET} ({hash_value}){empty_buf}")

    # Print destination files with no matches
    if non_matching_dest:
        print(f"\n{RED}DESTINATION FILES WITH NO MATCHES:{RESET}")
        for hash_value in non_matching_dest:
            for dest_file in dest_hashes[hash_value]:
                empty_buf = check_empty(hash_value)
                print(f"  {MAGENTA}{dest_file.absolute()}{RESET} ({hash_value}){empty_buf}")


@exception_handler
def main():
    """ handle command line arguments, run main logic"""
    parser = argparse.ArgumentParser( description="Compare SHA1 checksums between two directories", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument( "-s", "--source_dir", type=Path, default=Path("."), help="Source directory to compare")
    parser.add_argument( "-d", "--dest_dir", type=Path, required=True, help="Destination directory to compare against")
    
    args = parser.parse_args()
    
    # Validate directories exist
    if not args.source_dir.exists():
        print(f"{RED}Error:{RESET} Source directory '{args.source_dir}' does not exist")
        sys.exit(1)
        
    if not args.dest_dir.exists():
        print(f"{RED}Error:{RESET} Destination directory '{args.dest_dir}' does not exist")
        sys.exit(1)
    
    # Collect hashes from both directories
    print(f"{LIGHT_CYAN}Collecting hashes from source {BLUE}{args.source_dir}{RESET} ")
    source_hashes = collect_hashes(args.source_dir)
    
    print(f"{LIGHT_CYAN}Collecting hashes from destination {BLUE}{args.dest_dir}{RESET} ")
    dest_hashes = collect_hashes(args.dest_dir)
    
    # Compare and display results
    print(f"{LIGHT_CYAN}Comparing hashes...{RESET}")
    compare_directories(source_hashes, dest_hashes)

if __name__ == "__main__":
    main()
