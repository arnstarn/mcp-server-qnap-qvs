"""Async HTTP client for the QNAP Virtualization Station (QVS) REST API.

The QVS API lives at /qvs on the QNAP NAS and uses session-based auth with
CSRF token protection. This client handles login, session management, and
provides typed methods for all supported VM operations.

Tested on: QTS 5.x with Virtualization Station 3.x+
API reference: https://github.com/tmeckel/qnap-qvs-sdk-for-go (auto-generated from QNAP OpenAPI specs)
"""

from __future__ import annotations

import base64
import logging
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
    """Async client for QNAP Virtualization Station REST API."""

    def __init__(self, config: QVSConfig) -> None:
        self._config = config
        self._client: httpx.AsyncClient | None = None
        self._csrf_token: str | None = None

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
        """Authenticate to QVS and establish a session with CSRF token."""
        assert self._client is not None

        password_b64 = base64.b64encode(self._config.password.encode()).decode()

        response = await self._client.post(
            "/qvs/auth/login",
            data={"username": self._config.username, "password": password_b64},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if response.status_code != 200:
            raise QVSError(f"Login failed with status {response.status_code}: {response.text}", response.status_code)

        body = response.json()
        if body.get("status") != 0:
            raise QVSError(f"Login failed: {body.get('message', 'unknown error')}")

        # Extract CSRF token from cookies
        csrf = response.cookies.get("csrftoken")
        if not csrf:
            # Try from Set-Cookie header as fallback
            for cookie in self._client.cookies.jar:
                if cookie.name == "csrftoken":
                    csrf = cookie.value
                    break

        if not csrf:
            raise QVSError("Login succeeded but no CSRF token received")

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
            response = await self._client.request(method, path, headers=headers, **kwargs)
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

    # ── VM Operations ─────────────────────────────────────────────

    async def list_vms(self) -> dict[str, Any]:
        """List all virtual machines."""
        return await self._request("GET", "/qvs/vms")

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
