"""Configuration for QNAP QVS MCP server."""

from __future__ import annotations

import os


def _load_env_file() -> None:
    """Load variables from ENV_FILE into os.environ if they're not already set."""
    env_file = os.environ.get("ENV_FILE", "")
    if not env_file:
        return
    try:
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    key, val = key.strip(), val.strip()
                    if key not in os.environ or not os.environ[key]:
                        os.environ[key] = val
    except FileNotFoundError:
        pass


class QVSConfig:
    """Configuration loaded from environment variables."""

    def __init__(self) -> None:
        _load_env_file()

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
