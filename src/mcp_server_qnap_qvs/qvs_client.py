"""Async HTTP client for the QNAP Virtualization Station (QVS) REST API.

The QVS API lives at /qvs on the QNAP NAS. Authentication is a two-step process:
1. QTS login via /cgi-bin/authLogin.cgi → returns NAS_SID session cookie
2. QVS login via /qvs/auth/login with NAS_SID → returns csrftoken + sessionid cookies

All subsequent QVS API calls require all three cookies plus an X-CSRFToken header.

Tested on: QuTS hero h5.x with Virtualization Station 4.1.x
API reference: https://github.com/tmeckel/qnap-qvs-sdk-for-go (auto-generated from QNAP OpenAPI specs)
"""

from __future__ import annotations

import base64
import logging
import re
from typing import Any

import httpx

from .config import QVSConfig

logger = logging.getLogger(__name__)


class QVSError(Exception):
    """Error from the QVS API."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class QVSClient:
    """Async client for QNAP Virtualization Station REST API.

    Uses two-step auth: QTS session → QVS session with CSRF token.
    """

    def __init__(self, config: QVSConfig) -> None:
        self._config = config
        self._client: httpx.AsyncClient | None = None
        self._csrf_token: str | None = None
        self._cookies: dict[str, str] = {}

    async def __aenter__(self) -> QVSClient:
        self._client = httpx.AsyncClient(
            base_url=self._config.base_url,
            verify=self._config.verify_ssl,
            timeout=30.0,
        )
        await self._login()
        return self

    async def __aexit__(self, exc_type: type | None, exc_val: Exception | None, exc_tb: Any) -> None:
        if self._client:
            try:
                await self._logout()
            except Exception:
                logger.debug("Logout failed during cleanup", exc_info=True)
            await self._client.aclose()
            self._client = None

    async def _login(self) -> None:
        """Two-step authentication: QTS login then QVS login."""
        assert self._client is not None

        # Step 1: QTS system login to get NAS_SID
        qts_response = await self._client.get(
            "/cgi-bin/authLogin.cgi",
            params={"user": self._config.username, "plain_pwd": self._config.password},
        )
        if qts_response.status_code != 200:
            raise QVSError(
                f"QTS login failed with status {qts_response.status_code}",
                qts_response.status_code,
            )

        sid_match = re.search(r"<authSid><!\[CDATA\[(.+?)\]\]></authSid>", qts_response.text)
        auth_match = re.search(r"<authPassed><!\[CDATA\[(\d+)\]\]></authPassed>", qts_response.text)

        if not auth_match or auth_match.group(1) != "1":
            raise QVSError("QTS login failed: invalid credentials")
        if not sid_match:
            raise QVSError("QTS login failed: no session ID returned")

        nas_sid = sid_match.group(1)
        self._cookies["NAS_SID"] = nas_sid
        logger.info("QTS login successful, SID obtained")

        # Step 2: QVS login with NAS_SID to get CSRF token + session
        password_b64 = base64.b64encode(self._config.password.encode()).decode()
        qvs_response = await self._client.post(
            "/qvs/auth/login",
            data={"username": self._config.username, "password": password_b64},
            cookies=self._cookies,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if qvs_response.status_code != 200:
            raise QVSError(
                f"QVS login failed with status {qvs_response.status_code}",
                qvs_response.status_code,
            )

        # Collect QVS cookies (csrftoken, sessionid)
        for name, value in qvs_response.cookies.items():
            self._cookies[name] = value

        csrf = self._cookies.get("csrftoken")
        if not csrf:
            raise QVSError("QVS login completed but no CSRF token received")

        self._csrf_token = csrf
        logger.info("QVS login successful for user %s", self._config.username)

    async def _logout(self) -> None:
        """End the QVS session."""
        await self._request("POST", "/qvs/auth/logout")

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Make an authenticated request to the QVS API."""
        assert self._client is not None

        headers = kwargs.pop("headers", {})
        if self._csrf_token:
            headers["X-CSRFToken"] = self._csrf_token
            headers["Referer"] = f"{self._config.base_url}/qvs/"

        try:
            response = await self._client.request(
                method, path, headers=headers, cookies=self._cookies, **kwargs
            )
        except httpx.RequestError as e:
            raise QVSError(f"Request to {path} failed: {e}") from e

        if response.status_code >= 400:
            raise QVSError(
                f"QVS API error {response.status_code} on {method} {path}: {response.text}",
                response.status_code,
            )

        if not response.content:
            return {"status": 0}

        return response.json()

    # ── Host Info (QTS API) ─────────────────────────────────────────

    async def get_host_resources(self) -> dict[str, Any]:
        """Get host CPU and memory info from QTS sysinfo API."""
        assert self._client is not None
        response = await self._client.get(
            "/cgi-bin/management/manaRequest.cgi",
            params={"sid": self._cookies.get("NAS_SID", ""), "subfunc": "sysinfo"},
        )
        if response.status_code != 200:
            return {}

        text = response.text
        result: dict[str, Any] = {}

        patterns = {
            "cpu_model": r"<cpu_model><!\[CDATA\[(.+?)\]\]></cpu_model>",
            "cpu_usage_percent": r"<cpu_usage><!\[CDATA\[(.+?)\]\]></cpu_usage>",
            "total_memory_mb": r"<total_memory><!\[CDATA\[(.+?)\]\]></total_memory>",
            "free_memory_mb": r"<free_memory><!\[CDATA\[(.+?)\]\]></free_memory>",
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, text)
            if match:
                val = match.group(1)
                if key in ("total_memory_mb", "free_memory_mb"):
                    result[key] = round(float(val))
                elif key == "cpu_usage_percent":
                    result[key] = float(val.replace(" %", "").strip())
                else:
                    result[key] = val

        # Extract CPU core count from model string (e.g. "Quad-core" -> 4)
        cpu_model = result.get("cpu_model", "")
        core_words = {"Dual": 2, "Quad": 4, "Hexa": 6, "Octa": 8}
        for word, count in core_words.items():
            if word in cpu_model:
                result["cpu_cores"] = count
                result["cpu_threads"] = count * 2  # SMT
                break

        return result

    # ── VM Operations ─────────────────────────────────────────────

    async def list_vms(self) -> dict[str, Any]:
        """List all virtual machines."""
        return await self._request("GET", "/qvs/vms")

    async def create_vm(self, **fields: Any) -> dict[str, Any]:
        """Create a new VM."""
        return await self._request("POST", "/qvs/vms", json=fields)

    async def get_vm(self, vm_id: str) -> dict[str, Any]:
        """Get details of a specific VM."""
        return await self._request("GET", f"/qvs/vms/{vm_id}")

    async def get_vm_states(self) -> dict[str, Any]:
        """Get lightweight state info for all VMs."""
        return await self._request("GET", "/qvs/vms/states")

    async def start_vm(self, vm_id: str) -> dict[str, Any]:
        """Start a VM."""
        return await self._request("POST", f"/qvs/vms/{vm_id}/start")

    async def shutdown_vm(self, vm_id: str) -> dict[str, Any]:
        """Graceful shutdown of a VM."""
        return await self._request("POST", f"/qvs/vms/{vm_id}/shutdown")

    async def force_shutdown_vm(self, vm_id: str) -> dict[str, Any]:
        """Force shutdown a VM immediately."""
        return await self._request("POST", f"/qvs/vms/{vm_id}/forceshutdown")

    async def reset_vm(self, vm_id: str) -> dict[str, Any]:
        """Reset/restart a VM."""
        return await self._request("POST", f"/qvs/vms/{vm_id}/reset")

    async def suspend_vm(self, vm_id: str) -> dict[str, Any]:
        """Suspend a VM."""
        return await self._request("POST", f"/qvs/vms/{vm_id}/suspend")

    async def resume_vm(self, vm_id: str) -> dict[str, Any]:
        """Resume a suspended VM."""
        return await self._request("POST", f"/qvs/vms/{vm_id}/resume")

    async def get_vm_ips(self, vm_id: str) -> dict[str, Any]:
        """Get IP addresses assigned to a VM."""
        return await self._request("GET", f"/qvs/vms/{vm_id}/ips")

    # ── Disk Operations ───────────────────────────────────────────

    async def list_vm_disks(self, vm_id: str) -> dict[str, Any]:
        """List disks attached to a VM."""
        return await self._request("GET", f"/qvs/vms/{vm_id}/disks")

    # ── VM Hardware Info ──────────────────────────────────────────

    async def get_vm_adapters(self, vm_id: str) -> dict[str, Any]:
        """Get network adapters (interfaces) for a VM."""
        return await self._request("GET", f"/qvs/vms/{vm_id}/adapters")

    async def get_vm_graphics(self, vm_id: str) -> dict[str, Any]:
        """Get graphics/VNC console info for a VM."""
        return await self._request("GET", f"/qvs/vms/{vm_id}/graphics")

    async def get_vm_cdroms(self, vm_id: str) -> dict[str, Any]:
        """Get CD-ROM drives for a VM."""
        return await self._request("GET", f"/qvs/vms/{vm_id}/cdroms")

    async def get_vm_usbs(self, vm_id: str) -> dict[str, Any]:
        """Get USB passthrough devices for a VM."""
        return await self._request("GET", f"/qvs/vms/{vm_id}/usbs")

    # ── Images / ISOs ─────────────────────────────────────────────

    async def list_images(self) -> dict[str, Any]:
        """List available ISO images on the NAS."""
        return await self._request("GET", "/qvs/images")

    # ── Logs ──────────────────────────────────────────────────────

    async def get_logs(self, limit: int = 50, page: int = 1) -> dict[str, Any]:
        """Get QVS event/audit logs."""
        return await self._request("GET", "/qvs/logs", params={"limit": limit, "page": page})

    # ── VM CRUD ────────────────────────────────────────────────────

    async def update_vm(self, vm_id: str, **fields: Any) -> dict[str, Any]:
        """Update VM settings (PATCH). VM should be stopped for most changes."""
        return await self._request("PATCH", f"/qvs/vms/{vm_id}", json=fields)

    async def delete_vm(self, vm_id: str) -> dict[str, Any]:
        """Delete/destroy a VM permanently."""
        return await self._request("DELETE", f"/qvs/vms/{vm_id}")

    async def clone_vm(self, vm_id: str, name: str) -> dict[str, Any]:
        """Clone a VM."""
        return await self._request("POST", f"/qvs/vms/{vm_id}/clone", json={"name": name})

    async def export_vm(self, vm_id: str, path: str) -> dict[str, Any]:
        """Export a VM to a path on the NAS."""
        return await self._request("POST", f"/qvs/vms/{vm_id}/export", json={"path": path})

    # ── Disk CRUD ─────────────────────────────────────────────────

    async def update_disk(self, vm_id: str, disk_id: str, **fields: Any) -> dict[str, Any]:
        """Update a disk (e.g. resize). VM should be stopped."""
        return await self._request("PATCH", f"/qvs/vms/{vm_id}/disks/{disk_id}", json=fields)

    async def delete_disk(self, vm_id: str, disk_id: str) -> dict[str, Any]:
        """Delete/detach a disk from a VM."""
        return await self._request("DELETE", f"/qvs/vms/{vm_id}/disks/{disk_id}")

    # ── Network Adapter CRUD ──────────────────────────────────────

    async def add_adapter(self, vm_id: str, **fields: Any) -> dict[str, Any]:
        """Add a network adapter to a VM."""
        return await self._request("POST", f"/qvs/vms/{vm_id}/adapters", json=fields)

    async def update_adapter(self, vm_id: str, adapter_id: str, **fields: Any) -> dict[str, Any]:
        """Update a network adapter on a VM."""
        return await self._request("PATCH", f"/qvs/vms/{vm_id}/adapters/{adapter_id}", json=fields)

    async def delete_adapter(self, vm_id: str, adapter_id: str) -> dict[str, Any]:
        """Remove a network adapter from a VM."""
        return await self._request("DELETE", f"/qvs/vms/{vm_id}/adapters/{adapter_id}")

    # ── CDROM Operations ──────────────────────────────────────────

    async def update_cdrom(self, vm_id: str, cdrom_id: str, **fields: Any) -> dict[str, Any]:
        """Update a CD-ROM (mount/unmount ISO)."""
        return await self._request("PATCH", f"/qvs/vms/{vm_id}/cdroms/{cdrom_id}", json=fields)

    # ── Shutdown Progress ─────────────────────────────────────────

    async def get_stopping_progress(self) -> dict[str, Any]:
        """Get shutdown progress for all VMs."""
        return await self._request("GET", "/qvs/vms/stopping_progress")

    # ── Snapshot Operations ───────────────────────────────────────

    async def list_snapshots(self, vm_id: str) -> dict[str, Any]:
        """List snapshots for a VM."""
        return await self._request("GET", f"/qvs/vms/{vm_id}/snapshots")

    async def create_snapshot(self, vm_id: str, name: str | None = None) -> dict[str, Any]:
        """Create a snapshot of a VM."""
        data: dict[str, Any] = {}
        if name:
            data["name"] = name
        return await self._request("POST", f"/qvs/vms/{vm_id}/snapshots", json=data)

    async def get_snapshot(self, vm_id: str, snapshot_id: str) -> dict[str, Any]:
        """Get details of a specific snapshot."""
        return await self._request("GET", f"/qvs/vms/{vm_id}/snapshots/{snapshot_id}")

    async def revert_snapshot(self, vm_id: str, snapshot_id: str) -> dict[str, Any]:
        """Revert a VM to a snapshot."""
        return await self._request("POST", f"/qvs/vms/{vm_id}/snapshots/{snapshot_id}/revert")

    async def delete_snapshot(self, vm_id: str, snapshot_id: str) -> dict[str, Any]:
        """Delete a snapshot."""
        return await self._request("DELETE", f"/qvs/vms/{vm_id}/snapshots/{snapshot_id}")
