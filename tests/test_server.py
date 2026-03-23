"""Tests for MCP server tool registration and safety guards."""

from mcp_server_qnap_qvs.server import mcp


def test_tools_registered():
    """Verify all expected tools are registered."""
    tools = {t.name for t in mcp._tool_manager.list_tools()}
    expected = {
        # Read
        "list_vms",
        "get_vm",
        "get_vm_states",
        "get_vm_ips",
        "list_vm_disks",
        "get_vm_adapters",
        "get_vm_graphics",
        "get_vm_cdroms",
        "get_vm_usbs",
        "list_images",
        "get_qvs_logs",
        "get_overview",
        "get_stopping_progress",
        # VM CRUD
        "create_vm",
        "update_vm",
        "delete_vm",
        "clone_vm",
        "export_vm",
        # Disk
        "resize_disk",
        "delete_disk",
        # ISO
        "mount_iso",
        "unmount_iso",
        # Guest agent install
        "install_guest_agent_ssh",
        "install_guest_agent_virsh",
        # Lifecycle
        "start_vm",
        "shutdown_vm",
        "force_shutdown_vm",
        "reset_vm",
        "suspend_vm",
        "resume_vm",
        # Snapshots
        "list_snapshots",
        "create_snapshot",
        "revert_snapshot",
        "delete_snapshot",
    }
    assert expected.issubset(tools), f"Missing tools: {expected - tools}"


def test_destructive_tools_have_confirm():
    """All tools marked DESTRUCTIVE must accept a confirm parameter."""
    for tool in mcp._tool_manager.list_tools():
        desc = tool.description or ""
        if "DESTRUCTIVE" in desc:
            param_names = [p.get("name", k) for k, p in (tool.parameters or {}).get("properties", {}).items()]
            assert "confirm" in param_names, f"Tool {tool.name} is DESTRUCTIVE but has no confirm param"
