# mcp-server-qnap-qvs

[![PyPI](https://img.shields.io/pypi/v/mcp-server-qnap-qvs)](https://pypi.org/project/mcp-server-qnap-qvs/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-server-qnap-qvs)](https://pypi.org/project/mcp-server-qnap-qvs/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

MCP server for [QNAP Virtualization Station (QVS)](https://www.qnap.com/en/software/virtualization-station) — manage virtual machines, snapshots, disks, and more on your QNAP NAS via the QVS REST API.

> **Note:** This is not an official QNAP product. The QVS REST API is undocumented — this project is based on reverse-engineering the web UI and the [qnap-qvs-sdk-for-go](https://github.com/tmeckel/qnap-qvs-sdk-for-go) project.

## Compatibility

| Component | Tested | Expected |
|-----------|--------|----------|
| QTS | — | 5.1.0+ |
| QuTS hero | h5.2.8 | h5.1.0+ |
| Virtualization Station | 4.1.x | 3.x+ |
| NAS hardware | TS-873AeU (AMD Ryzen V1500B) | x86 with VT-x/AMD-V |

ARM-based QNAP models do not support Virtualization Station.

## Features

**33 tools** across 5 categories:

- **VM lifecycle** — start, shutdown, force-stop, reset, suspend, resume
- **VM management** — update settings (CPU, memory, name, auto-start), delete, clone, export
- **VM info** — details, state, IPs, adapters, graphics/VNC, CD-ROMs, USBs
- **Disk & ISO** — list disks, resize, delete, mount/unmount ISOs
- **Snapshots** — list, create, revert, delete
- **Analysis** — resource overview dashboard (host CPU/RAM utilization, per-VM summary with networking), QVS audit logs, shutdown progress
- **Safety** — all destructive operations require explicit `confirm=true`

## Quick Start

### Install

```bash
# Via uvx (recommended)
uvx mcp-server-qnap-qvs

# Or via pip
pip install mcp-server-qnap-qvs
```

Requires Python 3.10+.

### Configure

Set environment variables:

```bash
export QNAP_HOST=your-nas.local    # NAS hostname or IP
export QNAP_PORT=443               # HTTPS port (default: 443)
export QNAP_USERNAME=admin         # QTS admin username
export QNAP_PASSWORD=your-pass     # QTS password
export QNAP_VERIFY_SSL=false       # Set true if using valid TLS cert
```

Or use a `.env` file (see `.env.example`).

### MCP Client Configuration

#### Claude Code (`~/.claude.json`)

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

#### Claude Desktop (`claude_desktop_config.json`)

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

## Available Tools

### Read-Only (13 tools)

| Tool | Description |
|------|-------------|
| `list_vms` | List all VMs with full details |
| `get_vm` | Get detailed info for a single VM |
| `get_vm_states` | Lightweight status overview of all VMs |
| `get_vm_ips` | Get IP addresses of a VM (requires QEMU guest agent) |
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

## Authentication

The QVS REST API uses a two-step session-based authentication:

1. **QTS login** (`/cgi-bin/authLogin.cgi`) — returns a `NAS_SID` session cookie
2. **QVS login** (`/qvs/auth/login`) with the `NAS_SID` — returns `csrftoken` + `sessionid` cookies

All subsequent API calls include all three cookies plus an `X-CSRFToken` header. The client handles this automatically.

## Safety

All destructive operations require `confirm=true`. Without it, the tool returns a preview of what it would do — no changes are made. This prevents accidental VM deletions, shutdowns, or snapshot reverts.

## Development

```bash
git clone https://github.com/arnstarn/mcp-server-qnap-qvs.git
cd mcp-server-qnap-qvs
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/ tests/
```

## API Reference

The QVS REST API is not officially documented. This project's API knowledge comes from:

- [tmeckel/qnap-qvs-sdk-for-go](https://github.com/tmeckel/qnap-qvs-sdk-for-go) — Go SDK auto-generated from QNAP's internal OpenAPI specs
- [QTS HTTP API Authentication v5.1.0](https://eu1.qnap.com/dev/QTS_HTTP_API-Authentication_v5.1.0.pdf) — Official QNAP auth docs
- Browser DevTools inspection of the Virtualization Station web UI

## License

MIT
