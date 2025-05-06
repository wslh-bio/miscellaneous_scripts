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

- Python 3.10+
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


# SSH Tunnel Configuration and Usage

SSH tunnels provide a secure way to access network resources over an established ssh connection. 

### Understanding SSH Tunnels

SSH tunnels create encrypted channels between your local machine and remote servers. Tunnels provide a secure transport to resources which are not otherwise directly available to a host. When used with gmount, they allow you to:

- Access shares behind firewalls or bastion hosts
- Provide an encrypted connection for the data while in transit
- Provde additional authentication using ssh

### SSH Configuration Example

Add these lines to your SSH configuration file (typically `~/.ssh/config`):

# SSH tunnel configuration example
### smb over ssh

The configuration below tells `ssh` how to handle a connection to the host `mybastion`. To intiate the connection you would enter `ssh mybastion`. The ssh application will lookup the host in the config file and apply the configured items to the connection automatically, such as using port 2222 instead of the default port 22. This allows for a much simpler command line leaving all the configuration complexity in the config file.

Otherwise, your ssh command might look something like this:
`ssh mybastion.myorg.edu -p 22222 -L 4451:files.myhost.edut:445 -L 4452:data.myhost.edu:445 -L backups.myhost.edu:445`

`LocalForward` is a keyword that tells ssh to claim a port to use locally (must not be in current use) and forward all traffic received on that port, through the secure SSH tunnel, to the specified remote host and port. After establishing the ssh connection, you can access the remote server over the configured tunnel port. In the case below, this would be `localhost:4451` <> `files.myhost.edu:445`

```bash
Host mybastion
  Hostname mybastion.myorg.edu
  Port 2222
  LocalForward 4451   files.myhost.edu:445      <-- local port 4451 will forward all traffic to files.myhost.edu on destination port 445
  LocalForward 4452   data.myhost.edu:445       <-- local port 4452 will do the same for data.myhost.edu
  LocalForward 4453   backups.myhost.edu:445    <-- local port 4453 for backups.myhost.edu
```

Each line creates a separate tunnel to a remote server (from the perspective of the bastion host):
- Listens on a local port (4451, 4452, 4453)
- Forwards traffic to the specified remote server and port (445)
- Encrypts all traffic through the SSH connection

After establishing the initial ssh connection, the tunnels will be connected to the remote serviers automatically. It's OK if the hostnames in the ssh tunnel configuration are not resolvable from your device. ssh will use the bastion host's DNS resolovers, after connecting, to find the appropriate hosts to tunnel to. If the DNS hostname is not resolvable, the connection will fail. In this cirucumstance, the IP address may be substituted for the hostname.  If the connection still fails, more investigation will be needed in terms of network or remote host routes, firewalls, access controls, etc.

The initial ssh connection will need to remain open for the tunnels to stay active. Some organizations will restrict access to only the tunnel connections so a terminal session may not be available and you may receive a connection error.  To connect without "logging in" try the `-N` ssh argument. This will only connect to the bastion host and attempt to intiate the tunnel connections without starting a shell/login on the bastion. The `-N` flag will not show any output about the connection so it can be difficult to determine if there are any connection problems. If you suspect issues with the connection, try adding the `-v` or `-vvv` flags along with `-N` and you will see debugging information printed about the connection in real-time.

A [diagram here](ssh-tunnel.gif) illustrates how the various parameters in the ssh connection information are applied.
- an ssh connection is established to the bastion host.
- ssh applies the tunnel configurations to connect to the remote hosts via the established ssh connection.

# gmount configuration example
Gmount was developed explicitly for use with ssh tunnels so the example configuration below uses locally forwarded ports as reviewed above. 
```json
{
  "mounts": {
    "gvfs": [
      {
        "comment": "remote files from host blah"                  # free-form comment
        "host"   : "localhost:4451",                              # hostname or a localhost tunnel and port
        "share"  : "share_name",                                  # the name of the windows share to mount
        "local"  : "/home/@USERNAME/mounts/share",                # where the symlink to the mount will be created*
        "domain" : "YOURDOMAIN"                                   # the windows Active Directory domain to use
      }
    ]
  }
}

* GFVS mounts everything under /var/run/user/$UID/gvfs and is not configurable
```

# Mounting an s3 bucket with gmount (via rclone)
If you install `rclone`, you can configure a second backend in gmount for an s3 bucket. First, configure rclone for the aws account containing the bucket you want to use. Then, add that gclone reference to the `gmount.json` file. An example config may now be extended for s3 to look something like:
```json
{
  "mounts": {
    "gvfs": [
      {
        "comment": "remote files from host blah"
        "host"   : "localhost:4451",
        "share"  : "share_name",
        "local"  : "/home/@USERNAME/mounts/share",
        "domain" : "YOURDOMAIN"
      }
    ],
    "s3": [
      {         
        "comment": "S3 293 bucket",                               # free-form comment
        "backend": "rclone",                                      # default is rclone. maybe something else in the future
        "config" : "/home/@USERNAME/.config/rclone/rclone.conf",  # where to find the rclone config for this bucket
        "local"  : "/home/@USERNAME/mnt/my-bucket-0382",          # where the bucket will be mounted
        "remote" : "acloud:/my-bucket-0382"                       # the rclone config block name and literal bucket name to mount
      }
    ]
  }
}
```

The associated rclone configuration block below was configured for `env_auth`. This means rclone will expect to find the needed AWS connection information exported to the environment. Prior to running gmount with an S3 configuration, you will need to export `AWS_ACCESS_KEY_ID`, `AWS_REGION` and `AWS_SECRET_ACCESS_KEY` to your environment.  Other authentication methods exist in rclone if this one is not suitable but be aware that saving AWS credentials to a file may pose a substantial security risk to your org.
```
[acloud]
type      = s3
provider  = AWS
env_auth  = true
region    = us-east-2
acl       = private
server_side_encryption = AES256
```


### Important Notes

- Make sure SSH connections are established and active before mounting shares
- Use the same port numbers in both SSH and gmount configurations
- The ssh login/tunnel must remain active for the duration of the mount
- Save often/backup regularly. Network disruption of mounted filesystem can lead to file corruption.

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
   - Uses `gio mount` to connect to remote SMB shares
   - Uses `rclone` for connecting to S3 buckets
   - Handles authentication via password prompt (or exported environment vars in case of rclone)
   - Creates symbolic links to the GVFS mount points under `/run/user/$UID/gvfs`

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
