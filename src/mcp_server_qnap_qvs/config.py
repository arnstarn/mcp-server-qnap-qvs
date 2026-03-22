"""Configuration for QNAP QVS MCP server."""

from __future__ import annotations

import os


class QVSConfig:
    """Configuration loaded from environment variables."""

    def __init__(self) -> None:
        self.host = os.environ.get("QNAP_HOST", "")
        self.port = int(os.environ.get("QNAP_PORT", "443"))
        self.username = os.environ.get("QNAP_USERNAME", "")
        self.password = os.environ.get("QNAP_PASSWORD", "")
        self.verify_ssl = os.environ.get("QNAP_VERIFY_SSL", "false").lower() in ("true", "1", "yes")

        if not self.host:
            raise ValueError("QNAP_HOST environment variable is required")
        if not self.username:
            raise ValueError("QNAP_USERNAME environment variable is required")
        if not self.password:
            raise ValueError("QNAP_PASSWORD environment variable is required")

    @property
    def base_url(self) -> str:
        return f"https://{self.host}:{self.port}"
