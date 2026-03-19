# Linux CLI Utilities

A collection of command-line scripts for Linux.

## Table of Contents
* [HostCheck](#hostcheck) — host ping, port and DNS checks

---

## HostCheck

### Description
`hostcheck.sh` takes a comma separated list of hosts to check for ping, DNS, and well known service ports. It's designed to provide a better view of a host's availability than just ping. It validates DNS integrity, checks for CNAME chains, and runs a connection test to specific TCP ports to see if common services are available. The original concept started as a shell script then run through gemini to colorize, format and clean up. 

### Key Features
* **DNS Validation:** Does both forward (A record) and reverse (PTR record) lookups.
* **DNS Consistency:** Checks if reverse DNS matches forward DNS (potential server config issue).
* **CNAME Discovery:** Shows full CNAME chain for alias hostnames.
* **Smart Port Scanning:** Checks common service ports (SSH, HTTP, MySQL, etc.) using `netcat` if available and `/dev/tcp` as fallback.
* **Summary Table:** Generates a summary of checked targets at the end of the run.

### Usage

```bash
./hostcheck.sh -n <host1,host2,IP1,...> [-w <timeout_seconds>]
```

| Flag | Description | Default |
| :--- | :--- | :--- |
| `-n` | **Required.** Comma-separated list of hostnames or IPv4 addresses. | N/A |
| `-w` | Timeout in seconds for DNS queries, pings, and port checks. | 2 |

### Dependencies
* `bash`
* `dig` (usually part of the `dnsutils` or `bind9-host` package)
* `ping` (iputils)
* `nc` (netcat - nice to have, not required)

---
