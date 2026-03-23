"""Password hashing, session management, and authentication."""

from __future__ import annotations

import hashlib
import http.cookies
import os
import secrets

from .constants import SESSION_SECRET, UI_PASSWORD_FILE


def hash_password(pw: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}:{pw}".encode()).hexdigest()
    return f"{salt}:{h}"


def verify_password(pw: str, stored: str) -> bool:
    if ":" not in stored:
        return False
    salt, expected = stored.split(":", 1)
    return hashlib.sha256(f"{salt}:{pw}".encode()).hexdigest() == expected


def has_password() -> bool:
    return os.path.exists(UI_PASSWORD_FILE)


def save_password(pw: str) -> None:
    with open(UI_PASSWORD_FILE, "w") as f:
        f.write(hash_password(pw))


def check_password(pw: str) -> bool:
    try:
        with open(UI_PASSWORD_FILE) as f:
            return verify_password(pw, f.read().strip())
    except FileNotFoundError:
        return False


def make_session_token(pw_hash: str) -> str:
    return hashlib.sha256(f"{SESSION_SECRET}:{pw_hash}".encode()).hexdigest()[:32]


def valid_session(cookie_header: str) -> bool:
    if not has_password():
        return True
    try:
        c = http.cookies.SimpleCookie(cookie_header)
        tok = c.get("mcp_qvs_session")
        if not tok:
            return False
        with open(UI_PASSWORD_FILE) as f:
            return tok.value == make_session_token(f.read().strip())
    except Exception:
        return False


def get_session_cookie(pw: str) -> str | None:
    """Verify password and return session cookie value, or None."""
    if not check_password(pw):
        return None
    with open(UI_PASSWORD_FILE) as f:
        return make_session_token(f.read().strip())
