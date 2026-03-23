"""Config UI package for mcp-server-qnap-qvs.

Login uses QNAP QTS credentials — no separate config UI password needed.
Sessions timeout after 30 minutes (configurable via SESSION_TIMEOUT env var).
"""

from __future__ import annotations

import socketserver

from .constants import UI_HOST, UI_PORT, VERSION
from .handler import Handler


def main() -> None:
    """Entry point for the config UI server."""
    with socketserver.TCPServer((UI_HOST, UI_PORT), Handler) as s:
        print(f"Config UI v{VERSION} on http://{UI_HOST}:{UI_PORT}")
        if UI_HOST == "127.0.0.1":
            print("  Localhost only. Set CONFIG_UI_HOST=0.0.0.0 for network access.")
        print("  Login with your QNAP admin credentials.")
        s.serve_forever()
