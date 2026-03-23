"""Authentication using QNAP QTS credentials.

Sessions are cookie-based with a configurable timeout (default 30 minutes,
matching QNAP's default session timeout).
"""

from __future__ import annotations

import hashlib
import http.cookies
import time

from .constants import SESSION_SECRET, SESSION_TIMEOUT


def _make_token(username: str, login_time: float) -> str:
    """Create a session token from username + login time + secret."""
    raw = f"{SESSION_SECRET}:{username}:{login_time}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def create_session(username: str) -> tuple[str, float]:
    """Create a new session. Returns (token, login_time)."""
    login_time = time.time()
    token = _make_token(username, login_time)
    return token, login_time


# In-memory session store: token -> (username, login_time)
_sessions: dict[str, tuple[str, float]] = {}


def store_session(token: str, username: str, login_time: float) -> None:
    _sessions[token] = (username, login_time)


def get_session(cookie_header: str) -> str | None:
    """Return the username if the session is valid, None otherwise."""
    try:
        c = http.cookies.SimpleCookie(cookie_header)
        tok = c.get("mcp_qvs_session")
        if not tok:
            return None
        session = _sessions.get(tok.value)
        if not session:
            return None
        username, login_time = session
        if time.time() - login_time > SESSION_TIMEOUT:
            del _sessions[tok.value]
            return None
        return username
    except Exception:
        return None


def clear_session(cookie_header: str) -> None:
    """Remove the session."""
    try:
        c = http.cookies.SimpleCookie(cookie_header)
        tok = c.get("mcp_qvs_session")
        if tok and tok.value in _sessions:
            del _sessions[tok.value]
    except Exception:
        pass


def session_cookie(token: str) -> str:
    """Build the Set-Cookie header value."""
    return f"mcp_qvs_session={token}; Path=/; HttpOnly; SameSite=Strict"


def clear_cookie() -> str:
    """Build a Set-Cookie that clears the session."""
    return "mcp_qvs_session=; Max-Age=0; Path=/; HttpOnly"
