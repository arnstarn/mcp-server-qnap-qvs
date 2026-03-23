"""Config UI package for mcp-server-qnap-qvs."""

from __future__ import annotations

import socketserver

from .constants import UI_HOST, UI_PORT, VERSION
from .handler import Handler


def main() -> None:
    """Entry point for the config UI server."""
    from .auth import has_password

    with socketserver.TCPServer((UI_HOST, UI_PORT), Handler) as s:
        print(f"Config UI v{VERSION} on http://{UI_HOST}:{UI_PORT}")
        if UI_HOST == "127.0.0.1":
            print("  Localhost only. Set CONFIG_UI_HOST=0.0.0.0 for network access.")
        if not has_password():
            print("  First visit will prompt for a config UI password.")
        s.serve_forever()
