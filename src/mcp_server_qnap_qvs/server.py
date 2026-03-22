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


# ── VM Hardware Info Tools ────────────────────────────────────────


@mcp.tool()
async def get_vm_adapters(vm_id: str) -> str:
    """Get network adapters for a virtual machine.

    Returns MAC addresses, bridge assignments, NIC model (virtio/e1000), and queue config.

    Args:
        vm_id: The VM identifier
    """
    try:
        client = await _get_client()
        result = await client.get_vm_adapters(vm_id)
        return _json(result)
    except QVSError as e:
        return _json({"error": str(e)})


@mcp.tool()
async def get_vm_graphics(vm_id: str) -> str:
    """Get graphics/VNC console info for a virtual machine.

    Returns VNC port, type, and whether password protection is enabled.

    Args:
        vm_id: The VM identifier
    """
    try:
        client = await _get_client()
        result = await client.get_vm_graphics(vm_id)
        return _json(result)
    except QVSError as e:
        return _json({"error": str(e)})


@mcp.tool()
async def get_vm_cdroms(vm_id: str) -> str:
    """Get CD-ROM drives and mounted ISOs for a virtual machine.

    Args:
        vm_id: The VM identifier
    """
    try:
        client = await _get_client()
        result = await client.get_vm_cdroms(vm_id)
        return _json(result)
    except QVSError as e:
        return _json({"error": str(e)})


@mcp.tool()
async def get_vm_usbs(vm_id: str) -> str:
    """Get USB passthrough devices attached to a virtual machine.

    Args:
        vm_id: The VM identifier
    """
    try:
        client = await _get_client()
        result = await client.get_vm_usbs(vm_id)
        return _json(result)
    except QVSError as e:
        return _json({"error": str(e)})


# ── Images / ISOs ────────────────────────────────────────────────


@mcp.tool()
async def list_images() -> str:
    """List ISO images available on the QNAP NAS for mounting to VMs."""
    try:
        client = await _get_client()
        result = await client.list_images()
        return _json(result)
    except QVSError as e:
        return _json({"error": str(e)})


# ── Logs ─────────────────────────────────────────────────────────


@mcp.tool()
async def get_qvs_logs(limit: int = 50, page: int = 1) -> str:
    """Get Virtualization Station event and audit logs.

    Shows VM starts, stops, resets, config changes, login events, errors, etc.

    Args:
        limit: Number of log entries to return (default 50)
        page: Page number for pagination (default 1)
    """
    try:
        client = await _get_client()
        result = await client.get_logs(limit=limit, page=page)
        return _json(result)
    except QVSError as e:
        return _json({"error": str(e)})


# ── Clone / Export ───────────────────────────────────────────────


@mcp.tool()
async def clone_vm(vm_id: str, name: str, confirm: bool = False) -> str:
    """DESTRUCTIVE: Clone a virtual machine.

    Creates a full copy of the VM with a new name. The source VM should
    ideally be stopped for a consistent clone.

    Args:
        vm_id: The source VM identifier
        name: Name for the cloned VM
        confirm: Must be true to execute. Returns a preview otherwise.
    """
    if not confirm:
        return _json({
            "warning": f"This will clone VM {vm_id} as '{name}'. Set confirm=true to proceed.",
            "action": "clone_vm",
            "vm_id": vm_id,
            "clone_name": name,
        })
    try:
        client = await _get_client()
        result = await client.clone_vm(vm_id, name)
        return _json({"action": "clone_vm", "vm_id": vm_id, "clone_name": name, "result": result})
    except QVSError as e:
        return _json({"error": str(e)})


@mcp.tool()
async def export_vm(vm_id: str, path: str, confirm: bool = False) -> str:
    """DESTRUCTIVE: Export a virtual machine to a path on the NAS.

    Exports the VM disk images and configuration to the specified shared folder path.

    Args:
        vm_id: The VM identifier
        path: Destination path on the NAS (e.g. 'shared://VMs/exports/')
        confirm: Must be true to execute. Returns a preview otherwise.
    """
    if not confirm:
        return _json({
            "warning": f"This will export VM {vm_id} to '{path}'. Set confirm=true to proceed.",
            "action": "export_vm",
            "vm_id": vm_id,
            "path": path,
        })
    try:
        client = await _get_client()
        result = await client.export_vm(vm_id, path)
        return _json({"action": "export_vm", "vm_id": vm_id, "path": path, "result": result})
    except QVSError as e:
        return _json({"error": str(e)})


# ── VM Update / Delete ───────────────────────────────────────────


@mcp.tool()
async def update_vm(
    vm_id: str,
    name: str = "",
    cores: int = 0,
    memory_mb: int = 0,
    description: str = "",
    auto_start: str = "",
    auto_start_delay: int = -1,
    confirm: bool = False,
) -> str:
    """DESTRUCTIVE: Update virtual machine settings.

    The VM should be stopped before changing CPU or memory. Only non-empty/non-zero
    fields are applied — omit fields you don't want to change.

    Args:
        vm_id: The VM identifier
        name: New VM name (leave empty to keep current)
        cores: Number of vCPU cores (0 to keep current)
        memory_mb: Memory in MB (0 to keep current)
        description: New description (leave empty to keep current)
        auto_start: Auto-start policy: 'on', 'off', or 'last' (leave empty to keep current)
        auto_start_delay: Auto-start delay in seconds (-1 to keep current)
        confirm: Must be true to execute. Returns a preview otherwise.
    """
    fields: dict = {}
    if name:
        fields["name"] = name
    if cores > 0:
        fields["cores"] = cores
    if memory_mb > 0:
        fields["memory"] = memory_mb * 1024 * 1024
    if description:
        fields["description"] = description
    if auto_start:
        fields["auto_start"] = auto_start
    if auto_start_delay >= 0:
        fields["auto_start_delay"] = auto_start_delay

    if not fields:
        return _json({"error": "No fields to update. Provide at least one field to change."})

    if not confirm:
        return _json({
            "warning": f"This will update VM {vm_id} with: {fields}. Set confirm=true to proceed.",
            "action": "update_vm",
            "vm_id": vm_id,
            "changes": fields,
        })
    try:
        client = await _get_client()
        result = await client.update_vm(vm_id, **fields)
        return _json({"action": "update_vm", "vm_id": vm_id, "changes": fields, "result": result})
    except QVSError as e:
        return _json({"error": str(e)})


@mcp.tool()
async def delete_vm(vm_id: str, confirm: bool = False) -> str:
    """DESTRUCTIVE: Permanently delete a virtual machine and its disk images.

    This cannot be undone. The VM must be stopped first.

    Args:
        vm_id: The VM identifier
        confirm: Must be true to execute. Returns a preview otherwise.
    """
    if not confirm:
        return _json({
            "warning": f"This will PERMANENTLY DELETE VM {vm_id} and all its disks. Set confirm=true to proceed.",
            "action": "delete_vm",
            "vm_id": vm_id,
        })
    try:
        client = await _get_client()
        result = await client.delete_vm(vm_id)
        return _json({"action": "delete_vm", "vm_id": vm_id, "result": result})
    except QVSError as e:
        return _json({"error": str(e)})


# ── Disk Update / Delete ─────────────────────────────────────────


@mcp.tool()
async def resize_disk(vm_id: str, disk_id: str, size_gb: int, confirm: bool = False) -> str:
    """DESTRUCTIVE: Resize a virtual disk (expand only).

    The VM should be stopped. Disks can only be expanded, not shrunk.

    Args:
        vm_id: The VM identifier
        disk_id: The disk identifier (from list_vm_disks)
        size_gb: New disk size in GB
        confirm: Must be true to execute. Returns a preview otherwise.
    """
    if not confirm:
        return _json({
            "warning": f"This will resize disk {disk_id} on VM {vm_id} to {size_gb}GB. Set confirm=true to proceed.",
            "action": "resize_disk",
            "vm_id": vm_id,
            "disk_id": disk_id,
            "size_gb": size_gb,
        })
    try:
        client = await _get_client()
        result = await client.update_disk(vm_id, disk_id, size=size_gb * 1024 * 1024 * 1024)
        return _json({
            "action": "resize_disk", "vm_id": vm_id, "disk_id": disk_id,
            "size_gb": size_gb, "result": result,
        })
    except QVSError as e:
        return _json({"error": str(e)})


@mcp.tool()
async def delete_disk(vm_id: str, disk_id: str, confirm: bool = False) -> str:
    """DESTRUCTIVE: Remove and delete a disk from a virtual machine.

    This permanently deletes the disk image. The VM must be stopped.

    Args:
        vm_id: The VM identifier
        disk_id: The disk identifier
        confirm: Must be true to execute. Returns a preview otherwise.
    """
    if not confirm:
        return _json({
            "warning": (
                f"This will PERMANENTLY DELETE disk {disk_id} from VM {vm_id}. "
                "Set confirm=true to proceed."
            ),
            "action": "delete_disk",
            "vm_id": vm_id,
            "disk_id": disk_id,
        })
    try:
        client = await _get_client()
        result = await client.delete_disk(vm_id, disk_id)
        return _json({"action": "delete_disk", "vm_id": vm_id, "disk_id": disk_id, "result": result})
    except QVSError as e:
        return _json({"error": str(e)})


# ── Mount/Unmount ISO ────────────────────────────────────────────


@mcp.tool()
async def mount_iso(vm_id: str, cdrom_id: str, image_path: str, confirm: bool = False) -> str:
    """DESTRUCTIVE: Mount an ISO image to a VM's CD-ROM drive.

    Args:
        vm_id: The VM identifier
        cdrom_id: The CD-ROM drive identifier (from get_vm_cdroms)
        image_path: Path to ISO on NAS (e.g. 'shared://ISOs/ubuntu.iso')
        confirm: Must be true to execute. Returns a preview otherwise.
    """
    if not confirm:
        return _json({
            "warning": f"This will mount '{image_path}' to CD-ROM {cdrom_id} on VM {vm_id}. Set confirm=true.",
            "action": "mount_iso",
            "vm_id": vm_id,
            "cdrom_id": cdrom_id,
            "image_path": image_path,
        })
    try:
        client = await _get_client()
        result = await client.update_cdrom(vm_id, cdrom_id, path=image_path)
        return _json({"action": "mount_iso", "vm_id": vm_id, "result": result})
    except QVSError as e:
        return _json({"error": str(e)})


@mcp.tool()
async def unmount_iso(vm_id: str, cdrom_id: str, confirm: bool = False) -> str:
    """DESTRUCTIVE: Unmount/eject an ISO from a VM's CD-ROM drive.

    Args:
        vm_id: The VM identifier
        cdrom_id: The CD-ROM drive identifier
        confirm: Must be true to execute. Returns a preview otherwise.
    """
    if not confirm:
        return _json({
            "warning": f"This will eject the ISO from CD-ROM {cdrom_id} on VM {vm_id}. Set confirm=true.",
            "action": "unmount_iso",
            "vm_id": vm_id,
            "cdrom_id": cdrom_id,
        })
    try:
        client = await _get_client()
        result = await client.update_cdrom(vm_id, cdrom_id, path=None)
        return _json({"action": "unmount_iso", "vm_id": vm_id, "result": result})
    except QVSError as e:
        return _json({"error": str(e)})


# ── Analysis / Summary ───────────────────────────────────────────


@mcp.tool()
async def get_overview() -> str:
    """Get a summary dashboard of all VMs and resource usage.

    Returns: VM count, running/stopped breakdown, total vCPUs, memory,
    disk provisioned vs actual usage, per-VM summary with networking
    (adapters, MACs, IPs for running VMs).
    """
    try:
        client = await _get_client()
        result = await client.list_vms()
        vms = result.get("data", [])
        host = await client.get_host_resources()

        running = [v for v in vms if v.get("power_state") == "running"]
        stopped = [v for v in vms if v.get("power_state") == "stop"]
        other = [v for v in vms if v.get("power_state") not in ("running", "stop")]

        total_cores = sum(v.get("cores", 0) for v in vms)
        active_cores = sum(v.get("cores", 0) for v in running)
        total_mem = sum(v.get("memory", 0) for v in vms)
        active_mem = sum(v.get("memory", 0) for v in running)
        total_disk = sum(d.get("size", 0) for v in vms for d in v.get("disks", []))
        actual_disk = sum(d.get("actual_size", 0) for v in vms for d in v.get("disks", []))

        # Fetch IPs for running VMs (best-effort, requires guest agent)
        vm_ips: dict[int, list] = {}
        for v in running:
            try:
                ip_result = await client.get_vm_ips(str(v["id"]))
                if ip_result.get("status") == 0:
                    vm_ips[v["id"]] = ip_result.get("data", [])
            except QVSError:
                pass

        vm_summaries = []
        for v in vms:
            disks = v.get("disks", [])
            disk_total = sum(d.get("size", 0) for d in disks)
            disk_actual = sum(d.get("actual_size", 0) for d in disks)

            # Build network adapter summaries
            adapters = []
            for a in v.get("adapters", []):
                adapters.append({
                    "id": a.get("id"),
                    "mac": a.get("mac"),
                    "model": a.get("model"),
                    "bridge": a.get("bridge"),
                    "type": a.get("type"),
                })

            # Include IPs if available
            ips = vm_ips.get(v["id"])

            summary: dict = {
                "id": v["id"],
                "name": v["name"],
                "state": v.get("power_state"),
                "cores": v.get("cores"),
                "memory_mb": v.get("memory", 0) // 1024 // 1024,
                "os_type": v.get("os_type"),
                "auto_start": v.get("auto_start"),
                "disk_provisioned_gb": round(disk_total / 1024 / 1024 / 1024, 1),
                "disk_actual_gb": round(disk_actual / 1024 / 1024 / 1024, 1),
                "snapshots_size_gb": round(
                    sum(d.get("snapshots_size", 0) for d in disks) / 1024 / 1024 / 1024, 1
                ),
                "network": {
                    "adapters": adapters,
                    "ips": ips if ips else (
                        "not running" if v.get("power_state") != "running" else "guest agent required"
                    ),
                },
            }
            vm_summaries.append(summary)

        # Build resource summary with host totals and utilization %
        host_threads = host.get("cpu_threads", 0)
        host_mem_mb = host.get("total_memory_mb", 0)
        host_free_mb = host.get("free_memory_mb", 0)
        alloc_mem_mb = total_mem // 1024 // 1024
        active_mem_mb = active_mem // 1024 // 1024

        resources: dict = {
            "vcpus_allocated": total_cores,
            "vcpus_active": active_cores,
            "memory_allocated_mb": alloc_mem_mb,
            "memory_active_mb": active_mem_mb,
            "disk_provisioned_gb": round(total_disk / 1024 / 1024 / 1024, 1),
            "disk_actual_gb": round(actual_disk / 1024 / 1024 / 1024, 1),
        }

        if host:
            resources["host"] = {
                "cpu_model": host.get("cpu_model"),
                "cpu_cores": host.get("cpu_cores"),
                "cpu_threads": host_threads,
                "cpu_usage_percent": host.get("cpu_usage_percent"),
                "total_memory_mb": host_mem_mb,
                "free_memory_mb": host_free_mb,
                "used_memory_mb": host_mem_mb - host_free_mb,
            }
            if host_threads > 0:
                resources["utilization"] = {
                    "vcpu_allocated_pct": round(total_cores / host_threads * 100, 1),
                    "vcpu_active_pct": round(active_cores / host_threads * 100, 1),
                }
            if host_mem_mb > 0:
                resources["utilization"] = resources.get("utilization", {})
                resources["utilization"]["memory_allocated_pct"] = round(
                    alloc_mem_mb / host_mem_mb * 100, 1
                )
                resources["utilization"]["memory_active_pct"] = round(
                    active_mem_mb / host_mem_mb * 100, 1
                )

        overview = {
            "total_vms": len(vms),
            "running": len(running),
            "stopped": len(stopped),
            "other": len(other),
            "resources": resources,
            "vms": vm_summaries,
        }
        return _json(overview)
    except QVSError as e:
        return _json({"error": str(e)})


@mcp.tool()
async def get_stopping_progress() -> str:
    """Get the shutdown progress for all VMs.

    Useful during bulk shutdown operations to monitor which VMs are still stopping.
    """
    try:
        client = await _get_client()
        result = await client.get_stopping_progress()
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
    """Entry point for the MCP server.

    Supports two transport modes via MCP_TRANSPORT env var:
    - stdio (default): for local MCP clients (Claude Code, Claude Desktop)
    - sse: for remote MCP clients over HTTP (e.g. running on the QNAP NAS)

    SSE mode configuration:
    - MCP_TRANSPORT=sse
    - MCP_HOST=0.0.0.0 (default)
    - MCP_PORT=8445 (default)
    """
    import os

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    if transport == "sse":
        host = os.environ.get("MCP_HOST", "0.0.0.0")
        port = int(os.environ.get("MCP_PORT", "8445"))
        logger.info("Starting QNAP QVS MCP server (SSE on %s:%d)", host, port)
        mcp.run(transport="sse", host=host, port=port)
    else:
        logger.info("Starting QNAP QVS MCP server (stdio)")
        mcp.run()


if __name__ == "__main__":
    main()
