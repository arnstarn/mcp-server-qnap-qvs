"""MCP server for QNAP Virtualization Station (QVS).

Provides tools to manage virtual machines, snapshots, and disks on a QNAP NAS
running Virtualization Station via its REST API.

Tested on: QTS 5.x with Virtualization Station 3.x+
"""

from __future__ import annotations

import json
import logging

from mcp.server.fastmcp import FastMCP

from .config import QVSConfig
from .qvs_client import QVSClient, QVSError

logger = logging.getLogger(__name__)

mcp = FastMCP("qnap-qvs")

_client: QVSClient | None = None


async def _get_client() -> QVSClient:
    """Lazy-initialize and return the QVS client singleton."""
    global _client
    if _client is None:
        config = QVSConfig()
        _client = QVSClient(config)
        await _client.__aenter__()
    return _client


def _json(data: object) -> str:
    return json.dumps(data, indent=2, default=str)


# ── Read-Only Tools ───────────────────────────────────────────────


@mcp.tool()
async def list_vms() -> str:
    """List all virtual machines on the QNAP NAS with their status.

    Returns VM names, IDs, states (running/stopped/suspended), and basic resource info.
    """
    try:
        client = await _get_client()
        result = await client.list_vms()
        return _json(result)
    except QVSError as e:
        return _json({"error": str(e)})


@mcp.tool()
async def get_vm(vm_id: str) -> str:
    """Get detailed information about a specific virtual machine.

    Args:
        vm_id: The VM identifier (numeric ID from list_vms)
    """
    try:
        client = await _get_client()
        result = await client.get_vm(vm_id)
        return _json(result)
    except QVSError as e:
        return _json({"error": str(e)})


@mcp.tool()
async def get_vm_states() -> str:
    """Get a lightweight status overview of all VMs.

    Faster than list_vms — returns only VM IDs and their current state
    (running, stopped, suspended, etc.).
    """
    try:
        client = await _get_client()
        result = await client.get_vm_states()
        return _json(result)
    except QVSError as e:
        return _json({"error": str(e)})


@mcp.tool()
async def get_vm_ips(vm_id: str) -> str:
    """Get the IP addresses assigned to a virtual machine.

    Args:
        vm_id: The VM identifier
    """
    try:
        client = await _get_client()
        result = await client.get_vm_ips(vm_id)
        return _json(result)
    except QVSError as e:
        return _json({"error": str(e)})


@mcp.tool()
async def list_vm_disks(vm_id: str) -> str:
    """List all disks attached to a virtual machine.

    Args:
        vm_id: The VM identifier
    """
    try:
        client = await _get_client()
        result = await client.list_vm_disks(vm_id)
        return _json(result)
    except QVSError as e:
        return _json({"error": str(e)})


# ── VM Lifecycle Tools (require confirm=true) ─────────────────────


@mcp.tool()
async def start_vm(vm_id: str) -> str:
    """Start a stopped or suspended virtual machine.

    Args:
        vm_id: The VM identifier
    """
    try:
        client = await _get_client()
        result = await client.start_vm(vm_id)
        return _json({"action": "start", "vm_id": vm_id, "result": result})
    except QVSError as e:
        return _json({"error": str(e)})


@mcp.tool()
async def shutdown_vm(vm_id: str, confirm: bool = False) -> str:
    """DESTRUCTIVE: Gracefully shut down a running virtual machine.

    Sends an ACPI shutdown signal to the guest OS. The VM must have guest tools
    or ACPI support for this to work. Use force_shutdown_vm if the guest is unresponsive.

    Args:
        vm_id: The VM identifier
        confirm: Must be true to execute. Returns a preview otherwise.
    """
    if not confirm:
        return _json({
            "warning": f"This will gracefully shut down VM {vm_id}. Set confirm=true to proceed.",
            "action": "shutdown",
            "vm_id": vm_id,
        })
    try:
        client = await _get_client()
        result = await client.shutdown_vm(vm_id)
        return _json({"action": "shutdown", "vm_id": vm_id, "result": result})
    except QVSError as e:
        return _json({"error": str(e)})


@mcp.tool()
async def force_shutdown_vm(vm_id: str, confirm: bool = False) -> str:
    """DESTRUCTIVE: Immediately force-stop a virtual machine.

    Equivalent to pulling the power cord. May cause data loss or filesystem
    corruption in the guest. Use shutdown_vm for graceful shutdown first.

    Args:
        vm_id: The VM identifier
        confirm: Must be true to execute. Returns a preview otherwise.
    """
    if not confirm:
        return _json({
            "warning": f"This will FORCE STOP VM {vm_id} immediately. Risk of data loss. Set confirm=true to proceed.",
            "action": "force_shutdown",
            "vm_id": vm_id,
        })
    try:
        client = await _get_client()
        result = await client.force_shutdown_vm(vm_id)
        return _json({"action": "force_shutdown", "vm_id": vm_id, "result": result})
    except QVSError as e:
        return _json({"error": str(e)})


@mcp.tool()
async def reset_vm(vm_id: str, confirm: bool = False) -> str:
    """DESTRUCTIVE: Reset (hard restart) a virtual machine.

    Equivalent to pressing the reset button. The VM is immediately restarted
    without graceful shutdown. May cause data loss.

    Args:
        vm_id: The VM identifier
        confirm: Must be true to execute. Returns a preview otherwise.
    """
    if not confirm:
        return _json({
            "warning": f"This will HARD RESET VM {vm_id}. Risk of data loss. Set confirm=true to proceed.",
            "action": "reset",
            "vm_id": vm_id,
        })
    try:
        client = await _get_client()
        result = await client.reset_vm(vm_id)
        return _json({"action": "reset", "vm_id": vm_id, "result": result})
    except QVSError as e:
        return _json({"error": str(e)})


@mcp.tool()
async def suspend_vm(vm_id: str) -> str:
    """Suspend a running virtual machine to memory.

    The VM state is saved and can be resumed later with resume_vm.

    Args:
        vm_id: The VM identifier
    """
    try:
        client = await _get_client()
        result = await client.suspend_vm(vm_id)
        return _json({"action": "suspend", "vm_id": vm_id, "result": result})
    except QVSError as e:
        return _json({"error": str(e)})


@mcp.tool()
async def resume_vm(vm_id: str) -> str:
    """Resume a suspended virtual machine.

    Args:
        vm_id: The VM identifier
    """
    try:
        client = await _get_client()
        result = await client.resume_vm(vm_id)
        return _json({"action": "resume", "vm_id": vm_id, "result": result})
    except QVSError as e:
        return _json({"error": str(e)})


# ── Snapshot Tools ────────────────────────────────────────────────


@mcp.tool()
async def list_snapshots(vm_id: str) -> str:
    """List all snapshots for a virtual machine.

    Args:
        vm_id: The VM identifier
    """
    try:
        client = await _get_client()
        result = await client.list_snapshots(vm_id)
        return _json(result)
    except QVSError as e:
        return _json({"error": str(e)})


@mcp.tool()
async def create_snapshot(vm_id: str, name: str = "", confirm: bool = False) -> str:
    """DESTRUCTIVE: Create a snapshot of a virtual machine.

    Captures the current state of the VM including memory (if running) and disks.

    Args:
        vm_id: The VM identifier
        name: Optional name for the snapshot
        confirm: Must be true to execute. Returns a preview otherwise.
    """
    if not confirm:
        return _json({
            "warning": f"This will create a snapshot of VM {vm_id}. Set confirm=true to proceed.",
            "action": "create_snapshot",
            "vm_id": vm_id,
            "name": name or "(auto-generated)",
        })
    try:
        client = await _get_client()
        result = await client.create_snapshot(vm_id, name=name or None)
        return _json({"action": "create_snapshot", "vm_id": vm_id, "result": result})
    except QVSError as e:
        return _json({"error": str(e)})


@mcp.tool()
async def revert_snapshot(vm_id: str, snapshot_id: str, confirm: bool = False) -> str:
    """DESTRUCTIVE: Revert a virtual machine to a previous snapshot.

    All changes since the snapshot was taken will be lost. The VM should be
    stopped before reverting.

    Args:
        vm_id: The VM identifier
        snapshot_id: The snapshot identifier
        confirm: Must be true to execute. Returns a preview otherwise.
    """
    if not confirm:
        return _json({
            "warning": (
                f"This will REVERT VM {vm_id} to snapshot {snapshot_id}. "
                "All changes since will be LOST. Set confirm=true to proceed."
            ),
            "action": "revert_snapshot",
            "vm_id": vm_id,
            "snapshot_id": snapshot_id,
        })
    try:
        client = await _get_client()
        result = await client.revert_snapshot(vm_id, snapshot_id)
        return _json({"action": "revert_snapshot", "vm_id": vm_id, "snapshot_id": snapshot_id, "result": result})
    except QVSError as e:
        return _json({"error": str(e)})


@mcp.tool()
async def delete_snapshot(vm_id: str, snapshot_id: str, confirm: bool = False) -> str:
    """DESTRUCTIVE: Delete a snapshot permanently.

    This cannot be undone.

    Args:
        vm_id: The VM identifier
        snapshot_id: The snapshot identifier
        confirm: Must be true to execute. Returns a preview otherwise.
    """
    if not confirm:
        return _json({
            "warning": (
                f"This will PERMANENTLY DELETE snapshot {snapshot_id} from VM {vm_id}. "
                "Set confirm=true to proceed."
            ),
            "action": "delete_snapshot",
            "vm_id": vm_id,
            "snapshot_id": snapshot_id,
        })
    try:
        client = await _get_client()
        result = await client.delete_snapshot(vm_id, snapshot_id)
        return _json({"action": "delete_snapshot", "vm_id": vm_id, "snapshot_id": snapshot_id, "result": result})
    except QVSError as e:
        return _json({"error": str(e)})


def main() -> None:
    """Entry point for the MCP server."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    logger.info("Starting QNAP QVS MCP server")
    mcp.run()


if __name__ == "__main__":
    main()
