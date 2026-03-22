# mcp-server-qnap-qvs

MCP server for [QNAP Virtualization Station (QVS)](https://www.qnap.com/en/software/virtualization-station) — manage virtual machines, snapshots, and disks on your QNAP NAS via the QVS REST API.

> **Note:** This is not an official QNAP product. The QVS REST API is undocumented — this project is based on reverse-engineering the web UI and the [qnap-qvs-sdk-for-go](https://github.com/tmeckel/qnap-qvs-sdk-for-go) project.

## Compatibility

| Component | Tested | Expected |
|-----------|--------|----------|
| QTS | 5.x | 5.1.0+ |
| QuTS hero | — | h5.1.0+ |
| Virtualization Station | 3.x+ | 3.x+ |
| NAS hardware | x86 with VT-x/AMD-V | x86 only (ARM not supported) |

## Features

- **VM lifecycle** — list, start, shutdown, force-stop, reset, suspend, resume
- **VM info** — details, state, IP addresses, attached disks
- **Snapshots** — list, create, revert, delete
- **Safety guards** — destructive operations require explicit `confirm=true`
- **Session management** — automatic login, CSRF token handling, TLS with self-signed certs

## Quick Start

### Prerequisites

- Python 3.10+
- QNAP NAS with Virtualization Station installed
- Admin credentials for the NAS

### Install

```bash
# Via uvx (recommended)
uvx mcp-server-qnap-qvs

# Or via pip
pip install mcp-server-qnap-qvs
```

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

#### Claude Code (`~/.claude/settings.json`)

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

### Read-Only

| Tool | Description |
|------|-------------|
| `list_vms` | List all VMs with status |
| `get_vm` | Get detailed VM info |
| `get_vm_states` | Lightweight state overview of all VMs |
| `get_vm_ips` | Get IP addresses of a VM |
| `list_vm_disks` | List disks attached to a VM |
| `list_snapshots` | List snapshots for a VM |

### VM Lifecycle

| Tool | Description | Confirm? |
|------|-------------|----------|
| `start_vm` | Start a stopped VM | No |
| `shutdown_vm` | Graceful ACPI shutdown | Yes |
| `force_shutdown_vm` | Immediate force stop | Yes |
| `reset_vm` | Hard restart | Yes |
| `suspend_vm` | Suspend to memory | No |
| `resume_vm` | Resume suspended VM | No |

### Snapshots

| Tool | Description | Confirm? |
|------|-------------|----------|
| `create_snapshot` | Create a VM snapshot | Yes |
| `revert_snapshot` | Revert VM to snapshot | Yes |
| `delete_snapshot` | Delete a snapshot | Yes |

## Safety

All destructive operations (shutdown, force-stop, reset, snapshot revert/delete) require `confirm=true`. Without it, the tool returns a preview of what it would do.

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
