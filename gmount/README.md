# GVFS Mount Manager (gmount)

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

A Python utility for managing GNOME Virtual File System (GVFS) mounts for network shares using the `gio` command. This tool simplifies the process of mounting network drives by prompting for your password only once per invocation and creating easy to view symlinks in your home directory to easily access the mounted shares. Unmounting all shares is provided with the `-u` flag.

## Features

- Mount SMB network shares using GVFS
- Create symbolic links to mounted shares
- Password-protected authentication
- JSON-based configuration
- Color-coded terminal output
- Support for unmounting shares
- Environment variable expansion

## Prerequisites

- Python 3.6+
- Pexpect
- GNOME environment with GVFS support
- Required Python packages:
  - pexpect

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/wslh-bio/miscellaneous_scripts
   cd gmount
   ```

2. Install dependencies:
   ```bash
   pip install pexpect
   ```

3. Make the script executable:
   ```bash
   chmod +x gmount.py
   ```

## Configuration

Create a `gmount.json` file in the same directory as the script. This configuration file defines the network shares you want to mount and how they should be accessed.

### Configuration Structure

```json
{
  "mounts": {
    "gvfs": [
      {
        "host"   : "server.example.com",
        "share"  : "/share",
        "local"  : "/home/@USERNAME/mounts/example",
        "options": "optional_mount_options",
        "domain" : "optional_domain_name"
      }
    ]
  }
}
```

### Configuration Fields

- **mounts**: The root object containing all mount definitions
  - **gvfs**: An array of GVFS mount configurations (currently the only supported mount type)
    - **host**: The hostname or IP address of the remote file server
      - Identifies the network location of the server hosting the share
      - *Example*: `"fileserver.company.com"` or `"192.168.1.100"`
    
    - **share**: The share path on the remote server
      - Specifies which shared folder to access on the server
      - NOTE: `gio` mounts entire shares rather than specific subdirectories under the share
      - *Example*: `"/users"` or `"/public"`
    
    - **local**: The local path where the symlink to the gvfs mount will be created
      - Defines where the network share will appear in your local filesystem 
      - `gvfs` mounts are placed in `/var/run/user/${UID}/gvfs` by design so a symlink will be placed here instead
      - *Example*: `"/home/@USERNAME/mounts/server1"`
    
    - **options** (optional): Additional mount options
      - Provides extra parameters for customizing the mount behavior (currently unused)
      - *Example*: `"ro,uid=@FS_UID"` for read-only access
    
    - **domain** : Windows domain for authentication
      - Required when connecting to domain-controlled Windows shares
      - *Example*: `"WORKGROUP"` or `"MYDOMAIN"`

### Configuration Variables

The following variables are expanded automatically in the configuration:
- `@USERNAME`: Current logged-in username
  - *Example*: If current user is "john", `"/home/@USERNAME/mounts"` becomes `"/home/john/mounts"`

- `@FS_UID`: User ID
  - *Purpose*: Used for file ownership in mount options
  - *Example*: If user ID is 1000, `"uid=@FS_UID"` becomes `"uid=1000"`

- `@FS_GID`: Group ID
  - *Purpose*: Used for file group ownership in mount options
  - *Example*: If group ID is 1000, `"gid=@FS_GID"` becomes `"gid=1000"`

### Example Configuration

```json
{
  "mounts": {
    "gvfs": [
      {
        "host"  : "fileserver.ad.mydomain.com",
        "share" : "/users",
        "local" : "/home/@USERNAME/mounts/users",
        "domain": "WORKGROUP"
      },
      {
        "host"  : "nas.home.network",
        "share" : "/media",
        "local" : "/home/@USERNAME/mounts/media",
        "domain": "MYDOMAIN"
      },
      {
        "host"  : "localhost:4451",
        "share" : "jtidwell@hostname",
        "local" : "/home/@USERNAME/mounts/data",
        "domain": "MYDOMAIN"
      }
    ]
  }
}
```

## Usage

### Mount Shares
Mount with the default `gmount.json` in the current directory, or specifiy `-c` to point to a different config file.

```bash
./gmount.py

```

You will be prompted for your Windows AD password to authenticate with the remote server.

### Unmount Shares
Uses `gmount.json` in the current directory or use `-c` to point to a specific config somewhere else.

```bash
./gmount.py -u 
```

or

```bash
./gmount.py --umount
```

### Use Custom Configuration File

```bash
./gmount.py --config /path/to/custom_config.json
```

## How It Works

1. The script loads the configuration from the specified JSON file
2. For each configured mount point:
   - It checks if the mount already exists
   - Creates the local directory structure or symlink as needed
   - Uses `gio mount` to connect to the remote SMB share
   - Handles authentication via password prompt
   - Creates symbolic links to the actual GVFS mount points

## Classes and Components

- **PassManager**: Handles user authentication credentials
- **MountManager**: Main class for handling mount operations
- **Logging Functions**: Color-coded terminal output for various message types

## Error Handling

The script includes comprehensive error handling for common scenarios:
- Configuration file errors
- Authentication failures
- Network connectivity issues
- File permission problems
- Timeout handling


## License

This project is licensed under the GNU General Public License v3.0 - see the LICENSE file for details.

This program comes with ABSOLUTELY NO WARRANTY. This is free software, and you are welcome to redistribute it under certain conditions. See the GNU General Public License for more details.