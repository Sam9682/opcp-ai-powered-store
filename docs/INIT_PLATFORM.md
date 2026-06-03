# INIT_PLATFORM — User Guide

This document explains how to use `init_pltf.sh` to bootstrap a fresh server for the AI-SwAutoMorph platform.

## Overview

`init_pltf.sh` is a one-shot provisioning script that installs all system dependencies, configures networking, sets up Docker, and prepares the repository for deployment. It is designed to run on a fresh **Ubuntu** server (typically an OVHcloud instance).

## Prerequisites

| Requirement |                              Details                       |
|-------------|------------------------------------------------------------|
| OS          | Ubuntu 22.04+ (tested on OVHcloud VPS/dedicated)           |
| User        | A non-root user with `sudo` privileges                     |
| Network     | Internet access (public interface)                         |
| SSH key     | Configured for `git@github.com:Sam9682/opcp-ai-powered-store.git` |

## What the script installs

|         Component       |               Purpose               |
|-------------------------|-------------------------------------|
| Python 3 + pip + venv   | Application runtime                 |
| net-tools, unzip        | System utilities                    |
| Amazon Kiro CLI         | AI-assisted CLI chat                |
| OVH shai CLI            | OVHcloud management                 |
| AWS CLI v2              | S3-compatible object storage access |
| Terraform 1.14.5        | Infrastructure as code              |
| Docker + docker-compose | Container orchestration             |

## Usage

```bash
chmod +x init_pltf.sh
./init_pltf.sh
```

The script runs non-interactively. Each step prints a colored status:
- 🟢 `[OK]` — step completed successfully
- 🔴 `[ERROR]` — step failed
- 🟡 `[WARNING]` — non-critical issue or manual action needed

## Step-by-step breakdown

### 1. System dependencies

Installs Python 3, pip, venv, net-tools, and unzip via `apt`.

### 2. CLI tools

Installs three CLI tools:
- **Kiro CLI** — from `https://cli.kiro.dev/install`
- **OVH shai** — from the official OVH GitHub repository
- **AWS CLI v2** — from the official AWS distribution

### 3. Terraform

Downloads and installs Terraform `1.14.5` to `/usr/local/bin/`.

### 4. Network interface priorities

Automatically detects public and private network interfaces and configures netplan route metrics:
- **Public interface** → metric `50` (preferred for outbound traffic)
- **Private interface** → metric `200` (lower priority)

A backup of the original netplan configuration is created before any changes.

> This step is skipped if netplan is not found on the system.

### 5. Docker

Installs Docker Engine and docker-compose. Adds the current user to the `docker` group.

> You must log out and back in (or run `newgrp docker`) for the group change to take effect.

### 6. AWS credentials

Creates `~/.aws/config` and `~/.aws/credentials` with a placeholder profile `OVH-SWAUTOMORPH` pointing to the OVHcloud S3 endpoint (`s3.gra.io.cloud.ovh.net`).

### 7. Repository clone

Clones the `opcp-ai-powered-store` repository and initializes submodules.

### 8. Python virtual environment

Creates a `.venv` in the project directory and installs all dependencies from `requirements.txt`.

### 9. Final configuration

Creates the `logs/` directory and makes `setup_modsecurity_config.sh` executable.

## Post-installation steps

After the script completes, you **must** perform these manual steps:

### Configure the platform identity

Edit `./conf/deploy.ini`:

```ini
DOMAIN=yourdomain.com
PLTF_NAME=Your Platform Name

# Optional: secondary domains
SECONDARY_DOMAINS=other.com:other.com www.other.com:https://yourdomain.com:6137
```

### Add SSL certificates

Place your SSL files in the `ssl/` directory:

```
~/opcp-ai-powered-store/ssl/fullchain_domain.crt    # Full certificate chain
~/opcp-ai-powered-store/ssl/privateKey_domain.key   # Private key
```

### Configure S3 credentials

Edit `~/.aws/credentials` and replace the placeholder values:

```ini
[OVH-SWAUTOMORPH]
aws_access_key_id = YOUR_ACCESS_KEY
aws_secret_access_key = YOUR_SECRET_KEY
endpoint_url = https://s3.gra.io.cloud.ovh.net/
signature_version = s3v4
```

### Apply Docker group

Log out and back in, or run:

```bash
newgrp docker
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `Permission denied` on script | Run `chmod +x init_pltf.sh` |
| Docker commands fail after install | Log out/in or run `newgrp docker` |
| Git clone fails | Ensure your SSH key is added to GitHub |
| Netplan step skipped | Normal on non-netplan systems; configure routing manually |
| AWS CLI not found after install | Run `source ~/.bashrc` or open a new shell |

## Related documentation

- [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) — How to deploy the platform after initialization
- [ARCHITECTURE_GUIDE.md](./ARCHITECTURE_GUIDE.md) — Platform architecture overview
- [REPLICATION_GUIDE.md](./REPLICATION_GUIDE.md) — Multi-server replication setup
