"""Utility functions: env file I/O, port checks, QNAP API test, log reader."""

from __future__ import annotations

import collections
import socket
import ssl
import time
import urllib.parse
import urllib.request

from .constants import ENV_FILE, FIELDS, LOG_FILE, MCP_PORT, REGISTRY_FIELDS, START_TIME


def read_env() -> dict[str, str]:
    v: dict[str, str] = {}
    try:
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, val = line.partition("=")
                    v[k.strip()] = val.strip()
    except FileNotFoundError:
        pass
    return v


def write_env(values: dict[str, str]) -> None:
    with open(ENV_FILE, "w") as f:
        for key, _, default, _ in FIELDS:
            f.write(f"{key}={values.get(key, default)}\n")
        # Write registry fields if any are set
        has_registry = any(values.get(k) for k, _, _, _ in REGISTRY_FIELDS)
        if has_registry:
            f.write("\n# Docker registry (optional)\n")
            for key, _, default, _ in REGISTRY_FIELDS:
                val = values.get(key, default)
                if val:
                    f.write(f"{key}={val}\n")


def check_port(port: int = MCP_PORT) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except Exception:
        return False


def test_qnap(
    values: dict[str, str], require_admin: bool = False,
) -> tuple[bool, str]:
    """Test QNAP QTS authentication.

    If require_admin is True, also checks that the user is an admin.
    """
    try:
        host = values.get("QNAP_HOST", "")
        port = values.get("QNAP_PORT", "443")
        user = values.get("QNAP_USERNAME", "")
        pw = values.get("QNAP_PASSWORD", "")
        if not host or not user or not pw:
            return False, "Host, username, and password are required."
        ctx = ssl.create_default_context()
        if values.get("QNAP_VERIFY_SSL", "false") != "true":
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        url = (f"https://{host}:{port}/cgi-bin/authLogin.cgi"
               f"?user={urllib.parse.quote(user)}"
               f"&plain_pwd={urllib.parse.quote(pw)}")
        with urllib.request.urlopen(url, timeout=10, context=ctx) as r:
            body = r.read().decode()
            if "<authPassed><![CDATA[1]]>" not in body:
                return False, "Login failed — check username and password."
            if require_admin and "<isAdmin><![CDATA[1]]>" not in body:
                return False, "Admin access required. This user is not a QNAP administrator."
            return True, "Connected successfully."
    except Exception as e:
        return False, f"Connection failed: {e}"


def read_log(lines: int = 200) -> str:
    try:
        with open(LOG_FILE) as f:
            return "\n".join(collections.deque(f, maxlen=lines))
    except FileNotFoundError:
        return "(No log file found. The MCP server may not have started yet.)"


def check_latest_version() -> tuple[str, str]:
    """Check GitHub for the latest release version.

    Returns (latest_version, release_url) or ("unknown", "") on failure.
    """
    try:
        url = ("https://api.github.com/repos/arnstarn/"
               "mcp-server-qnap-qvs/releases/latest")
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            import json
            data = json.loads(r.read().decode())
            tag = data.get("tag_name", "")
            ver = tag.lstrip("v") if tag else "unknown"
            html_url = data.get("html_url", "")
            return ver, html_url
    except Exception:
        return "unknown", ""


def uptime() -> str:
    secs = int(time.time() - START_TIME)
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m {secs % 60}s"
    return f"{secs // 3600}h {(secs % 3600) // 60}m"
