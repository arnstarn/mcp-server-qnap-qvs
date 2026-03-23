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
    clear_cookie,
    clear_session,
    create_session,
    get_session,
    session_cookie,
    store_session,
)
from .constants import ENV_FILE, UI_BASE_PATH, VERSION
from .helpers import (
    check_latest_version,
    delete_backup,
    has_backup,
    read_env,
    restore_backup,
    test_qnap,
    write_env,
)
from .pages import (
    render_dashboard,
    render_login,
    render_logs,
    render_restore_choice,
    render_review,
    render_settings,
    render_success,
    render_wizard,
)


class Handler(http.server.BaseHTTPRequestHandler):
    def _strip_base(self, path: str) -> str:
        """Strip the base path prefix from the request path."""
        p = path.split("?")[0]
        if UI_BASE_PATH and p.startswith(UI_BASE_PATH):
            p = p[len(UI_BASE_PATH):]
        if not p or p == "":
            p = "/"
        return p

    def _get_user(self) -> str | None:
        """Return logged-in username or None."""
        return get_session(self.headers.get("Cookie", ""))

    def _require_auth(self) -> str | None:
        """Check auth. Returns username if ok, None if redirected to login."""
        user = self._get_user()
        if user:
            return user
        self._html(render_login())
        return None

    def do_GET(self) -> None:
        p = self._strip_base(self.path)

        if p == "/login":
            # If already logged in, redirect to dashboard
            if self._get_user():
                self._redirect(f"{UI_BASE_PATH}/")
                return
            self._html(render_login())
            return

        if p == "/logout":
            clear_session(self.headers.get("Cookie", ""))
            self.send_response(302)
            self.send_header("Location", f"{UI_BASE_PATH}/login")
            self.send_header("Set-Cookie", clear_cookie())
            self.end_headers()
            return

        user = self._require_auth()
        if not user:
            return

        env = read_env()
        is_first_run = not env.get("QNAP_USERNAME")

        if p in ("/", ""):
            if is_first_run:
                if has_backup():
                    self._html(render_restore_choice(user=user))
                else:
                    self._html(render_wizard(1, user=user))
            else:
                self._html(render_dashboard(user=user))
        elif p == "/restore-backup":
            if restore_backup():
                self._redirect(f"{UI_BASE_PATH}/")
            else:
                self._html(render_wizard(1, user=user))
        elif p == "/setup-fresh":
            delete_backup()
            self._html(render_wizard(1, user=user))
        elif p == "/settings":
            self._html(render_settings(env, user=user))
        elif p == "/logs":
            self._html(render_logs(user=user))
        elif p == "/reset":
            try:
                os.remove(ENV_FILE)
            except FileNotFoundError:
                pass
            self._html(render_settings(
                {}, "Configuration reset.", "info", user=user))
        elif p == "/api/generate-token":
            self._json({"token": secrets.token_urlsafe(48)})
        elif p == "/api/health":
            env = read_env()
            pw = env.get("QNAP_PASSWORD", "")
            has_real = (env.get("QNAP_HOST") and env.get("QNAP_USERNAME")
                        and pw and pw != "your-password-here")
            if has_real:
                ok, msg = test_qnap(env)
                self._json({"qnap_ok": ok, "qnap_msg": msg})
            else:
                self._json({"qnap_ok": False, "qnap_msg": "Not configured"})
        elif p == "/api/check-update":
            latest, release_url = check_latest_version()
            if latest == "unknown":
                self._json({"error": "Could not check for updates."})
            else:
                self._json({
                    "current": VERSION,
                    "latest": latest,
                    "update_available": latest != VERSION,
                    "release_url": release_url,
                })
        else:
            self._redirect(f"{UI_BASE_PATH}/")

    def do_POST(self) -> None:
        form = self._form()
        p = self._strip_base(self.path)

        if p == "/login":
            self._handle_login(form)
            return

        user = self._require_auth()
        if not user:
            return

        if p == "/api/test-connection":
            ok, msg = test_qnap(form)
            self._json({"ok": ok, "message": msg})
        elif p == "/api/update":
            self._handle_update()
        elif p == "/validate":
            ok, msg = test_qnap(form)
            self._html(render_review(form, ok, msg, user=user))
        elif p == "/confirm":
            write_env(form)
            self._html(render_success(form, user=user))
            threading.Thread(target=self._restart, daemon=True).start()
        elif p == "/wizard/1":
            ok, msg = test_qnap(form)
            if ok:
                self._html(render_wizard(2, form, user=user))
            else:
                self._html(render_wizard(1, form, msg, "err", user=user))
        elif p == "/wizard/2":
            if not form.get("MCP_AUTH_TOKEN"):
                self._html(render_wizard(
                    2, form, "Please set a token.", "err", user=user))
                return
            write_env(form)
            self._html(render_success(form, user=user))
            threading.Thread(target=self._restart, daemon=True).start()
        else:
            self._redirect(f"{UI_BASE_PATH}/")

    def _handle_login(self, form: dict[str, str]) -> None:
        username = form.get("username", "")
        password = form.get("password", "")

        if not username or not password:
            self._html(render_login("Username and password are required."))
            return

        # Validate against QNAP QTS auth API
        env = read_env()
        host = env.get("QNAP_HOST", "localhost")
        port = env.get("QNAP_PORT", "443")
        verify_ssl = env.get("QNAP_VERIFY_SSL", "false")

        ok, msg = test_qnap({
            "QNAP_HOST": host,
            "QNAP_PORT": port,
            "QNAP_USERNAME": username,
            "QNAP_PASSWORD": password,
            "QNAP_VERIFY_SSL": verify_ssl,
        }, require_admin=True)

        if not ok:
            # If no config exists yet, try localhost directly
            if not env.get("QNAP_HOST"):
                ok, msg = test_qnap({
                    "QNAP_HOST": "localhost",
                    "QNAP_PORT": "443",
                    "QNAP_USERNAME": username,
                    "QNAP_PASSWORD": password,
                    "QNAP_VERIFY_SSL": "false",
                }, require_admin=True)

        if not ok:
            self._html(render_login(msg))
            return

        token, login_time = create_session(username)
        store_session(token, username, login_time)
        self.send_response(302)
        self.send_header("Location", f"{UI_BASE_PATH}/")
        self.send_header("Set-Cookie", session_cookie(token))
        self.end_headers()

    def _redirect(self, location: str) -> None:
        self.send_response(302)
        self.send_header("Location", location)
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

    def _handle_update(self) -> None:
        """Pull latest Docker image and restart the container."""
        try:
            # The container can't pull its own image — signal the host
            # to restart the service (which pulls on start)
            self._json({
                "ok": True,
                "message": "Restarting service to pull the latest image...",
            })
            threading.Thread(target=self._restart, daemon=True).start()
        except Exception as e:
            self._json({"ok": False, "message": f"Update failed: {e}"})

    @staticmethod
    def _restart() -> None:
        time.sleep(3)
        os.system("kill 1 2>/dev/null")

    def log_message(self, fmt: str, *args: object) -> None:
        pass
