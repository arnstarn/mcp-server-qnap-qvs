"""HTTP request handler for the config UI."""

from __future__ import annotations

import http.server
import json
import os
import secrets
import threading
import time
import urllib.parse

from .auth import (
    check_password,
    has_password,
    make_session_token,
    save_password,
    valid_session,
)
from .constants import ENV_FILE, UI_PASSWORD_FILE
from .helpers import read_env, test_qnap, write_env
from .pages import (
    render_change_pw,
    render_dashboard,
    render_login,
    render_logs,
    render_review,
    render_settings,
    render_success,
    render_wizard,
)


class Handler(http.server.BaseHTTPRequestHandler):
    def _auth_ok(self) -> bool:
        if valid_session(self.headers.get("Cookie", "")):
            return True
        self._html(render_login(setup=not has_password()))
        return False

    def do_GET(self) -> None:
        p = self.path.split("?")[0]

        if p == "/login":
            self._html(render_login(setup=not has_password()))
            return

        if not self._auth_ok():
            return

        env = read_env()
        is_first_run = not env.get("QNAP_USERNAME")

        if p in ("/", ""):
            self._html(render_wizard(1) if is_first_run else render_dashboard())
        elif p == "/settings":
            self._html(render_settings(env))
        elif p == "/logs":
            self._html(render_logs())
        elif p == "/change-password":
            self._html(render_change_pw())
        elif p == "/reset":
            try:
                os.remove(ENV_FILE)
            except FileNotFoundError:
                pass
            self._html(render_settings({}, "Configuration reset.", "info"))
        elif p == "/logout":
            self.send_response(302)
            self.send_header("Location", "/login")
            self.send_header(
                "Set-Cookie", "mcp_qvs_session=; Max-Age=0; Path=/; HttpOnly"
            )
            self.end_headers()
        elif p == "/api/generate-token":
            self._json({"token": secrets.token_urlsafe(48)})
        else:
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()

    def do_POST(self) -> None:
        form = self._form()
        p = self.path.split("?")[0]

        if p == "/login":
            self._handle_login(form)
            return

        if p == "/change-password":
            if not self._auth_ok():
                return
            self._handle_change_pw(form)
            return

        if not self._auth_ok():
            return

        if p == "/api/test-connection":
            ok, msg = test_qnap(form)
            self._json({"ok": ok, "message": msg})
        elif p == "/validate":
            ok, msg = test_qnap(form)
            self._html(render_review(form, ok, msg))
        elif p == "/confirm":
            write_env(form)
            self._html(render_success(form))
            threading.Thread(target=self._restart, daemon=True).start()
        elif p == "/wizard/1":
            ok, msg = test_qnap(form)
            if ok:
                self._html(render_wizard(2, form))
            else:
                self._html(render_wizard(1, form, msg, "err"))
        elif p == "/wizard/2":
            if not form.get("MCP_AUTH_TOKEN"):
                self._html(render_wizard(2, form, "Please set a token.", "err"))
                return
            write_env(form)
            self._html(render_success(form))
            threading.Thread(target=self._restart, daemon=True).start()
        else:
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()

    def _handle_login(self, form: dict[str, str]) -> None:
        pw = form.get("password", "")
        if not has_password():
            confirm = form.get("confirm", "")
            if len(pw) < 6:
                self._html(render_login(
                    "Password must be at least 6 characters.", setup=True))
                return
            if pw != confirm:
                self._html(render_login("Passwords do not match.", setup=True))
                return
            save_password(pw)
        elif not check_password(pw):
            self._html(render_login("Incorrect password."))
            return

        with open(UI_PASSWORD_FILE) as f:
            tok = make_session_token(f.read().strip())
        self._redirect_with_cookie("/", tok)

    def _handle_change_pw(self, form: dict[str, str]) -> None:
        if not check_password(form.get("current", "")):
            self._html(render_change_pw("Current password is incorrect.", "err"))
            return
        new_pw = form.get("password", "")
        if len(new_pw) < 6:
            self._html(render_change_pw("Must be at least 6 characters.", "err"))
            return
        if new_pw != form.get("confirm", ""):
            self._html(render_change_pw("Passwords do not match.", "err"))
            return
        save_password(new_pw)
        with open(UI_PASSWORD_FILE) as f:
            tok = make_session_token(f.read().strip())
        self._redirect_with_cookie("/", tok)

    def _redirect_with_cookie(self, location: str, session_token: str) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header(
            "Set-Cookie",
            f"mcp_qvs_session={session_token}; Path=/; HttpOnly; SameSite=Strict",
        )
        self.end_headers()

    def _form(self) -> dict[str, str]:
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n).decode()
        return {k: v[0] for k, v in urllib.parse.parse_qs(body).items()}

    def _html(self, body: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode())

    def _json(self, data: dict) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    @staticmethod
    def _restart() -> None:
        time.sleep(3)
        os.system("kill 1 2>/dev/null")

    def log_message(self, fmt: str, *args: object) -> None:
        pass
