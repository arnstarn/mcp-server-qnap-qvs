"""Shared constants and configuration for the config UI."""

from __future__ import annotations

import os
import secrets
import time

try:
    from mcp_server_qnap_qvs import __version__
    VERSION = __version__
except Exception:
    VERSION = "unknown"

ENV_FILE = os.environ.get("ENV_FILE", "/config/.env")
LOG_FILE = os.environ.get("LOG_FILE", "/config/mcp-qvs.log")
UI_PORT = int(os.environ.get("CONFIG_UI_PORT", "8446"))
UI_HOST = os.environ.get("CONFIG_UI_HOST", "127.0.0.1")
MCP_PORT = int(os.environ.get("MCP_PORT", "8445"))
SESSION_SECRET = secrets.token_hex(32)
SESSION_TIMEOUT = int(os.environ.get("SESSION_TIMEOUT", "1800"))  # 30 min default
START_TIME = time.time()

FIELDS = [
    ("QNAP_HOST", "QNAP Hostname / IP", "localhost",
     "Use 'localhost' when running on the QNAP (default). Only change if running externally."),
    ("QNAP_PORT", "HTTPS Port", "443",
     "HTTPS port for the QNAP web UI. Default is 443."),
    ("QNAP_USERNAME", "QNAP Username", "",
     "Your QNAP admin username — same as your QNAP web UI login."),
    ("QNAP_PASSWORD", "QNAP Password", "",
     "Your QNAP admin password."),
    ("QNAP_VERIFY_SSL", "Verify SSL Certificate", "false",
     "Set 'true' if your NAS has a valid TLS cert. Usually 'false'."),
    ("MCP_AUTH_TOKEN", "MCP Auth Token", "",
     "Secret token for MCP clients. Click Generate or enter your own."),
]
