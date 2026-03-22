# mcp-server-qnap-qvs

[![PyPI](https://img.shields.io/pypi/v/mcp-server-qnap-qvs)](https://pypi.org/project/mcp-server-qnap-qvs/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-server-qnap-qvs)](https://pypi.org/project/mcp-server-qnap-qvs/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

MCP server for [QNAP Virtualization Station (QVS)](https://www.qnap.com/en/software/virtualization-station) — manage virtual machines, snapshots, disks, and more on your QNAP NAS via the QVS REST API.

> **Note:** This is not an official QNAP product. The QVS REST API is undocumented — this project is based on reverse-engineering the web UI and the [qnap-qvs-sdk-for-go](https://github.com/tmeckel/qnap-qvs-sdk-for-go) project.

## Prerequisites

Before you start, you need:

1. **QNAP NAS** with an x86 CPU (Intel or AMD with VT-x/AMD-V). ARM models do not support Virtualization Station.
2. **Virtualization Station** installed from the QNAP App Center.
3. **Admin credentials** — the username and password you use to log into the QNAP web UI. The server uses these to authenticate with the Virtualization Station API.
4. **Network access** — the machine running the server needs HTTPS access to your NAS (port 443 by default).
5. **Python 3.10+** on the machine running the server.

### Optional: QEMU Guest Agent

If you want the server to report VM IP addresses (via `get_vm_ips` and `get_overview`), install the QEMU guest agent **inside each VM**:

```bash
# For Ubuntu/Debian VMs:
sudo apt install qemu-guest-agent
sudo systemctl enable --now qemu-guest-agent
```

Without the guest agent, IP-related tools will return a helpful message explaining what's needed. Everything else works without it.

## Compatibility

| Component | Tested | Expected |
|-----------|--------|----------|
| QTS | — | 5.1.0+ |
| QuTS hero | h5.2.8 | h5.1.0+ |
| Virtualization Station | 4.1.x | 3.x+ |
| NAS hardware | x86 (AMD Ryzen) | x86 with VT-x/AMD-V |

## Features

**33 tools** across 6 categories:

- **VM lifecycle** — start, shutdown, force-stop, reset, suspend, resume
- **VM management** — update settings (CPU, memory, name, auto-start), delete, clone, export
- **VM info** — details, state, IPs, adapters, graphics/VNC, CD-ROMs, USBs
- **Disk & ISO** — list disks, resize, delete, mount/unmount ISOs
- **Snapshots** — list, create, revert, delete
- **Analysis** — resource overview dashboard (host CPU/RAM utilization, per-VM summary with networking), QVS audit logs, shutdown progress
- **Safety** — all destructive operations require explicit `confirm=true`

## Install

```bash
# Via uvx (recommended)
uvx mcp-server-qnap-qvs

# Or via pip
pip install mcp-server-qnap-qvs

# Or via Docker (for remote/NAS deployment)
docker pull ghcr.io/arnstarn/mcp-server-qnap-qvs:latest
```

## How Authentication Works

There are two separate authentication layers:

### 1. Server ↔ QNAP NAS (required)

The server authenticates to your QNAP's Virtualization Station API using your NAS admin credentials. This happens automatically — you just provide the credentials via environment variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `QNAP_HOST` | NAS hostname or IP address | Yes |
| `QNAP_PORT` | HTTPS port (default: `443`) | No |
| `QNAP_USERNAME` | QTS admin username | Yes |
| `QNAP_PASSWORD` | QTS admin password | Yes |
| `QNAP_VERIFY_SSL` | Verify TLS certificate (default: `false`) | No |

Most QNAP devices use self-signed certificates, so `QNAP_VERIFY_SSL=false` is typical. Set it to `true` if you've installed a valid certificate.

### 2. MCP Client ↔ Server (SSE mode only)

When running in **SSE mode** (remote/Docker), the server requires a Bearer token so only authorized MCP clients can connect:

| Variable | Description | Required |
|----------|-------------|----------|
| `MCP_AUTH_TOKEN` | A secret string you choose (like a password) | No |

- **If you set `MCP_AUTH_TOKEN`**: use that same value as the Bearer token in your MCP client config.
- **If you don't set it**: the server generates a random token on startup and prints it to the log. Copy it from there.
- **Stdio mode** (local, default): no token needed — the MCP client runs the server as a local process.

## Configuration

### Option A: Local Mode (stdio)

The server runs on your machine. Claude Code spawns it as a subprocess — no network, no token needed.

**Claude Code** (`~/.claude.json`):

```json
{
  "mcpServers": {
    "qnap-qvs": {
      "command": "uvx",
      "args": ["mcp-server-qnap-qvs"],
      "env": {
        "QNAP_HOST": "your-nas.local",
        "QNAP_USERNAME": "admin",
        "QNAP_PASSWORD": "your-password",
        "QNAP_VERIFY_SSL": "false"
      }
    }
  }
}
```

**Claude Desktop** (`claude_desktop_config.json`): same format as above.

### Option B: Remote Mode (SSE)

The server runs on the NAS (or any Docker host) and MCP clients connect over the network.

**Start the server:**

```bash
# Via Docker (recommended for NAS deployment)
docker run -d \
  -p 8445:8445 \
  -e QNAP_HOST=localhost \
  -e QNAP_USERNAME=admin \
  -e QNAP_PASSWORD=your-password \
  -e QNAP_VERIFY_SSL=false \
  -e MCP_AUTH_TOKEN=your-secret-token \
  ghcr.io/arnstarn/mcp-server-qnap-qvs:latest

# Or via Docker Compose
cp .env.example .env  # Edit .env with your credentials
docker-compose up -d

# Or directly with env vars
MCP_TRANSPORT=sse MCP_AUTH_TOKEN=your-secret-token mcp-server-qnap-qvs
```

When running on the NAS itself, set `QNAP_HOST=localhost` since the server and the API are on the same machine.

**Connect your MCP client:**

```json
{
  "mcpServers": {
    "qnap-qvs": {
      "url": "http://your-nas.local:8445/sse",
      "headers": {
        "Authorization": "Bearer your-secret-token"
      },
      "transportType": "sse"
    }
  }
}
```

### Option C: QNAP Container Station

1. Open Container Station on your QNAP NAS
2. Pull `ghcr.io/arnstarn/mcp-server-qnap-qvs:latest` or import the `docker-compose.yml`
3. Set environment variables (`QNAP_HOST=localhost`, `QNAP_USERNAME`, `QNAP_PASSWORD`, `MCP_AUTH_TOKEN`)
4. The server runs on port 8445 — connect from any MCP client on your network

### Option D: QPKG (App Center)

Install the QPKG directly on your QNAP NAS. It runs as a Docker container via Container Station.

**Step 1: Add the repository**

1. Open **App Center** on your QNAP
2. Click the **Settings** icon (gear, top-right)
3. Go to **App Repository**
4. Add this URL:
   ```
   https://raw.githubusercontent.com/arnstarn/mcp-server-qnap-qvs/main/qpkg/repo.xml
   ```
5. Click **Apply**

**Step 2: Install**

1. Search for **"MCP QVS Server"** in App Center
2. Click **Install**
3. Wait for the Docker image to download (first install only)

**Step 3: Configure credentials**

The QPKG creates a `.env` file with placeholder values. You need to edit it with your actual QNAP credentials.

SSH into your NAS and edit the `.env` file:

```bash
ssh your-username@your-nas.local

# Find the install path
QPKG_DIR=$(getcfg mcp-server-qnap-qvs Install_Path -f /etc/config/qpkg.conf)

# Edit the .env file (use vi, nano, or echo)
cat > "$QPKG_DIR/.env" << 'EOF'
QNAP_HOST=localhost
QNAP_PORT=443
QNAP_USERNAME=your-admin-username
QNAP_PASSWORD=your-admin-password
QNAP_VERIFY_SSL=false
MCP_AUTH_TOKEN=pick-any-secret-string-here
EOF

# Restart the service to pick up the new config
/etc/init.d/mcp-server-qnap-qvs.sh restart
```

Replace `your-admin-username` and `your-admin-password` with the credentials you use to log into the QNAP web UI. The `MCP_AUTH_TOKEN` is any secret string you choose — you'll use it as the Bearer token in your MCP client config.

**Step 4: Connect your MCP client**

```json
{
  "mcpServers": {
    "qnap-qvs": {
      "url": "http://your-nas.local:8445/sse",
      "headers": {
        "Authorization": "Bearer pick-any-secret-string-here"
      },
      "transportType": "sse"
    }
  }
}
```

Use the same `MCP_AUTH_TOKEN` value you set in Step 3.

**Updating:** When a new version is released, the App Center will show an update. Or pull the latest Docker image manually:

```bash
ssh your-username@your-nas.local
CS_DIR=$(getcfg container-station Install_Path -f /etc/config/qpkg.conf)
${CS_DIR}/bin/docker pull ghcr.io/arnstarn/mcp-server-qnap-qvs:latest
/etc/init.d/mcp-server-qnap-qvs.sh restart
```

## Environment Variables Reference

| Variable | Description | Default | Used In |
|----------|-------------|---------|---------|
| `QNAP_HOST` | NAS hostname or IP | — | Both modes |
| `QNAP_PORT` | NAS HTTPS port | `443` | Both modes |
| `QNAP_USERNAME` | QTS admin username | — | Both modes |
| `QNAP_PASSWORD` | QTS admin password | — | Both modes |
| `QNAP_VERIFY_SSL` | Verify TLS cert | `false` | Both modes |
| `MCP_TRANSPORT` | Transport mode: `stdio` or `sse` | `stdio` | — |
| `MCP_HOST` | SSE listen address | `0.0.0.0` | SSE only |
| `MCP_PORT` | SSE listen port | `8445` | SSE only |
| `MCP_AUTH_TOKEN` | Bearer token for SSE auth | (auto-generated) | SSE only |

## Available Tools

### Read-Only (13 tools)

| Tool | Description |
|------|-------------|
| `list_vms` | List all VMs with full details |
| `get_vm` | Get detailed info for a single VM |
| `get_vm_states` | Lightweight status overview of all VMs |
| `get_vm_ips` | Get VM IP addresses (requires QEMU guest agent in the VM) |
| `list_vm_disks` | List disks attached to a VM |
| `get_vm_adapters` | Network interfaces — MAC, model, bridge |
| `get_vm_graphics` | VNC console info — port, password status |
| `get_vm_cdroms` | CD-ROM drives and mounted ISOs |
| `get_vm_usbs` | USB passthrough devices |
| `list_images` | Available ISO images on the NAS |
| `get_qvs_logs` | QVS audit/event logs (paginated) |
| `get_overview` | Dashboard — VM count, host resources, utilization %, per-VM summary with networking |
| `get_stopping_progress` | Monitor bulk shutdown operations |

### VM Lifecycle (6 tools)

| Tool | Description | Confirm? |
|------|-------------|----------|
| `start_vm` | Start a stopped VM | No |
| `shutdown_vm` | Graceful ACPI shutdown | Yes |
| `force_shutdown_vm` | Immediate force stop | Yes |
| `reset_vm` | Hard restart | Yes |
| `suspend_vm` | Suspend to memory | No |
| `resume_vm` | Resume suspended VM | No |

### VM Management (4 tools)

| Tool | Description | Confirm? |
|------|-------------|----------|
| `update_vm` | Change name, CPU, memory, auto-start, description | Yes |
| `delete_vm` | Permanently destroy a VM and its disks | Yes |
| `clone_vm` | Clone a VM with a new name | Yes |
| `export_vm` | Export a VM to a NAS path | Yes |

### Disks & ISOs (4 tools)

| Tool | Description | Confirm? |
|------|-------------|----------|
| `resize_disk` | Expand a virtual disk | Yes |
| `delete_disk` | Remove and delete a disk | Yes |
| `mount_iso` | Mount an ISO to a VM's CD-ROM | Yes |
| `unmount_iso` | Eject an ISO from a VM's CD-ROM | Yes |

### Snapshots (4 tools)

| Tool | Description | Confirm? |
|------|-------------|----------|
| `list_snapshots` | List snapshots for a VM | — |
| `create_snapshot` | Create a VM snapshot | Yes |
| `revert_snapshot` | Revert VM to a snapshot | Yes |
| `delete_snapshot` | Delete a snapshot | Yes |

## Safety

All destructive operations require `confirm=true`. Without it, the tool returns a preview of what it would do — no changes are made. This prevents accidental VM deletions, shutdowns, or snapshot reverts.

## Troubleshooting

### "QEMU guest agent is not installed or not running"

The `get_vm_ips` tool and the IP section of `get_overview` require the QEMU guest agent running inside the VM. Install it:

```bash
# Ubuntu/Debian
sudo apt install qemu-guest-agent && sudo systemctl enable --now qemu-guest-agent

# CentOS/RHEL
sudo yum install qemu-guest-agent && sudo systemctl enable --now qemu-guest-agent
```

All other tools work without the guest agent.

### "VM is not running"

IP addresses can only be retrieved from running VMs. Start the VM first with `start_vm`.

### Connection refused / timeout

- Verify the NAS is reachable: `curl -k https://your-nas.local:443`
- Check that Virtualization Station is installed and running in the QNAP App Center
- If using a non-default HTTPS port, set `QNAP_PORT` accordingly

### Login failed

- Verify your credentials work on the QNAP web UI
- The username and password are for the QNAP system admin account (the same one you use to log into QTS/QuTS hero)

## Development

```bash
git clone https://github.com/arnstarn/mcp-server-qnap-qvs.git
cd mcp-server-qnap-qvs
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/ tests/

# Build QPKG (requires Docker)
docker build -t qpkg-builder -f qpkg/Dockerfile.builder .
docker run --rm -v "$(pwd)/qpkg:/work" qpkg-builder
```

## API Reference

The QVS REST API is not officially documented. This project's API knowledge comes from:

- [tmeckel/qnap-qvs-sdk-for-go](https://github.com/tmeckel/qnap-qvs-sdk-for-go) — Go SDK auto-generated from QNAP's internal OpenAPI specs
- [QTS HTTP API Authentication v5.1.0](https://eu1.qnap.com/dev/QTS_HTTP_API-Authentication_v5.1.0.pdf) — Official QNAP auth docs
- Browser DevTools inspection of the Virtualization Station web UI

## License

MIT
