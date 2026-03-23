"""Lightweight web UI for configuring the MCP QVS server.

Runs on port 8446 (configurable via CONFIG_UI_PORT env var).
Provides a form to set QNAP credentials and MCP auth token,
with generate/copy buttons and setup instructions.
"""

from __future__ import annotations

import html
import http.server
import json
import os
import secrets
import socketserver
import threading
import time
import urllib.parse

ENV_FILE = os.environ.get("ENV_FILE", "/config/.env")
UI_PORT = int(os.environ.get("CONFIG_UI_PORT", "8446"))


def _detect_default_host() -> str:
    """Detect the best default for QNAP_HOST.

    If running on the QNAP itself (qpkg.conf exists), use 'localhost'.
    Otherwise return empty — the JS will fill it from the browser URL.
    """
    if os.path.exists("/etc/config/qpkg.conf"):
        return "localhost"
    return ""


FIELDS = [
    (
        "QNAP_HOST", "QNAP Hostname / IP", _detect_default_host(),
        "Hostname or IP of your QNAP NAS. Auto-detected from your browser.",
    ),
    (
        "QNAP_PORT", "HTTPS Port", "443",
        "HTTPS port for the QNAP web UI. Default is 443.",
    ),
    (
        "QNAP_USERNAME", "QNAP Username", "",
        "Your QNAP admin username — same as your QNAP web UI login.",
    ),
    (
        "QNAP_PASSWORD", "QNAP Password", "",
        "Your QNAP admin password.",
    ),
    (
        "QNAP_VERIFY_SSL", "Verify SSL Certificate", "false",
        "Set 'true' if your NAS has a valid TLS cert. Usually 'false'.",
    ),
    (
        "MCP_AUTH_TOKEN", "MCP Auth Token", "",
        "Secret token for MCP clients. Click Generate or enter your own.",
    ),
]

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background: #0d1117; color: #e6edf3; padding: 20px; }
.container { max-width: 640px; margin: 0 auto; }
h1 { color: #58a6ff; margin-bottom: 8px; font-size: 24px; }
.subtitle { color: #8b949e; margin-bottom: 24px; font-size: 14px; }
.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px;
        padding: 24px; margin-bottom: 16px; }
.field { margin-bottom: 20px; }
label { display: block; font-weight: 600; margin-bottom: 4px; font-size: 14px; }
.hint { color: #8b949e; font-size: 12px; margin-top: 4px; }
.input { width: 100%; padding: 8px 12px; background: #0d1117;
         border: 1px solid #30363d; border-radius: 6px;
         color: #e6edf3; font-size: 14px; }
.input:focus { border-color: #58a6ff; outline: none; }
select.input { appearance: auto; }
.input-row { display: flex; gap: 8px; align-items: center; }
.input-row .input { flex: 1; }
.btn { padding: 8px 16px; border-radius: 6px; border: 1px solid #30363d;
       background: #21262d; color: #e6edf3; cursor: pointer; font-size: 13px;
       white-space: nowrap; text-decoration: none; display: inline-block; }
.btn:hover { background: #30363d; }
.btn-primary { background: #238636; border-color: #238636; }
.btn-primary:hover { background: #2ea043; }
.btn-danger { background: #da3633; border-color: #da3633; }
.btn-danger:hover { background: #f85149; }
.btn-sm { padding: 4px 12px; font-size: 12px; }
.actions { display: flex; gap: 12px; justify-content: flex-end; margin-top: 20px; }
.message { border-radius: 6px; padding: 12px; margin-bottom: 16px; font-size: 14px; }
.message-info { background: #1f6feb22; border: 1px solid #1f6feb; color: #58a6ff; }
.message-success { background: #23863622; border: 1px solid #238636; color: #3fb950; }
.message-error { background: #da363322; border: 1px solid #da3633; color: #f85149; }
.setup-info { background: #161b22; border: 1px solid #30363d; border-radius: 8px;
              padding: 20px; margin-bottom: 16px; }
.setup-info h2 { color: #58a6ff; font-size: 16px; margin-bottom: 12px; }
.setup-info p { color: #8b949e; font-size: 13px; line-height: 1.6; margin-bottom: 8px; }
.setup-info code { background: #0d1117; padding: 2px 6px; border-radius: 4px;
                   font-size: 12px; color: #e6edf3; }
.step { display: flex; gap: 12px; margin-bottom: 12px; }
.step-num { background: #238636; color: white; width: 24px; height: 24px;
            border-radius: 50%; display: flex; align-items: center;
            justify-content: center; font-size: 12px; font-weight: 700;
            flex-shrink: 0; }
.step-text { color: #c9d1d9; font-size: 13px; line-height: 1.5; }
.client-config { background: #0d1117; border: 1px solid #30363d; border-radius: 6px;
                 padding: 12px; margin-top: 12px; font-family: monospace;
                 font-size: 12px; color: #e6edf3; white-space: pre; overflow-x: auto; }
.copy-block { position: relative; }
.copy-block button { position: absolute; top: 8px; right: 8px; }
.review-table { width: 100%; border-collapse: collapse; }
.review-table td { padding: 8px 12px; border-bottom: 1px solid #30363d;
                   font-size: 13px; vertical-align: top; }
.review-table td:first-child { color: #8b949e; width: 160px; font-weight: 600; }
.review-table td:last-child { color: #e6edf3; word-break: break-all; }
.masked { color: #8b949e; }
"""

JS_MAIN = """
function toggleVis(fieldId, btnId) {
    const f = document.getElementById('field_' + fieldId);
    const b = document.getElementById(btnId);
    if (f.type === 'password') { f.type = 'text'; b.textContent = 'Hide'; }
    else { f.type = 'password'; b.textContent = 'Show'; }
}
function generateToken() {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
    let token = '';
    const arr = new Uint8Array(48);
    crypto.getRandomValues(arr);
    arr.forEach(b => token += chars[b % chars.length]);
    document.getElementById('field_MCP_AUTH_TOKEN').value = token;
    updateClientConfig();
}
function copyToken() {
    const f = document.getElementById('field_MCP_AUTH_TOKEN');
    navigator.clipboard.writeText(f.value).then(() => f.select());
}
function copyConfig() {
    navigator.clipboard.writeText(document.getElementById('clientConfig').textContent);
}
function updateClientConfig() {
    const token = document.getElementById('field_MCP_AUTH_TOKEN').value || 'your-token-here';
    const host = window.location.hostname;
    const config = JSON.stringify({
        mcpServers: { "qnap-qvs": {
            url: "http://" + host + ":8445/sse",
            headers: { Authorization: "Bearer " + token },
            transportType: "sse"
        }}
    }, null, 2);
    document.getElementById('clientConfig').textContent = config;
}
document.querySelectorAll('input').forEach(el => el.addEventListener('input', updateClientConfig));

// Auto-detect QNAP host from browser URL — only if no saved value exists
(function() {
    const hostField = document.getElementById('field_QNAP_HOST');
    if (hostField && (!hostField.value || hostField.value === 'localhost')) {
        const browserHost = window.location.hostname;
        if (browserHost && browserHost !== 'localhost' && browserHost !== '127.0.0.1') {
            // User is accessing via the NAS IP/hostname — that IS the QNAP
            hostField.value = browserHost;
            hostField.dataset.autoDetected = 'true';
        }
    }
})();

updateClientConfig();
"""


def read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    values[key.strip()] = val.strip()
    except FileNotFoundError:
        pass
    return values


def write_env(values: dict[str, str]) -> None:
    with open(ENV_FILE, "w") as f:
        for key, _, default, _ in FIELDS:
            val = values.get(key, default)
            f.write(f"{key}={val}\n")


def validate_connection(values: dict[str, str]) -> tuple[bool, str]:
    """Try connecting to QNAP to validate credentials."""
    try:
        import ssl
        import urllib.request

        host = values.get("QNAP_HOST", "")
        port = values.get("QNAP_PORT", "443")
        username = values.get("QNAP_USERNAME", "")
        password = values.get("QNAP_PASSWORD", "")

        if not host or not username or not password:
            return False, "Host, username, and password are required."

        ctx = ssl.create_default_context()
        if values.get("QNAP_VERIFY_SSL", "false") != "true":
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        url = f"https://{host}:{port}/cgi-bin/authLogin.cgi"
        url += f"?user={urllib.parse.quote(username)}"
        url += f"&plain_pwd={urllib.parse.quote(password)}"

        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            body = resp.read().decode()
            if "<authPassed><![CDATA[1]]>" in body:
                return True, "Connected to QNAP successfully."
            return False, "Login failed — check username and password."
    except Exception as e:
        return False, f"Connection failed: {e}"


def render_form(values: dict[str, str], message: str = "", msg_type: str = "info") -> str:
    has_config = bool(values.get("QNAP_USERNAME") and values.get("QNAP_PASSWORD"))

    rows = ""
    for key, label, default, hint_text in FIELDS:
        val = html.escape(values.get(key, default))
        extra = ""

        if key == "MCP_AUTH_TOKEN":
            extra = (
                '<button type="button" class="btn btn-sm" onclick="generateToken()">'
                "Generate</button>"
                '<button type="button" class="btn btn-sm" onclick="copyToken()">'
                "Copy</button>"
            )

        if "PASSWORD" in key or key == "MCP_AUTH_TOKEN":
            show_id = f"show_{key}"
            inp = (
                f'<input type="password" name="{key}" '
                f'value="{val}" class="input" id="field_{key}">'
                f'<button type="button" class="btn btn-sm" id="{show_id}" '
                f'onclick="toggleVis(\'{key}\', \'{show_id}\')">Show</button>'
            )
        elif key == "QNAP_VERIFY_SSL":
            sel_f = "selected" if val != "true" else ""
            sel_t = "selected" if val == "true" else ""
            inp = (
                f'<select name="{key}" class="input">'
                f'<option value="false" {sel_f}>false (self-signed, typical)</option>'
                f'<option value="true" {sel_t}>true (valid TLS cert)</option>'
                "</select>"
            )
        else:
            inp = (
                f'<input type="text" name="{key}" '
                f'value="{val}" class="input" id="field_{key}">'
            )

        rows += f"""
        <div class="field">
            <label>{html.escape(label)}</label>
            <div class="input-row">{inp}{extra}</div>
            <div class="hint">{html.escape(hint_text)}</div>
        </div>"""

    msg_html = ""
    if message:
        msg_html = (
            f'<div class="message message-{msg_type}">'
            f'{html.escape(message)}</div>'
        )

    if has_config and not message:
        msg_html = (
            '<div class="message message-success">'
            "Configuration loaded. Update any fields below and click Save, "
            "or click Reset to start fresh.</div>"
        )

    setup_steps = """
<div class="setup-info">
<h2>How It Works</h2>
<div class="step"><div class="step-num">1</div>
<div class="step-text">Enter your QNAP admin credentials below — the same
username and password you use to log into the QNAP web UI.</div></div>
<div class="step"><div class="step-num">2</div>
<div class="step-text">Set an MCP Auth Token — click <strong>Generate</strong>
to create a random one, or type your own.</div></div>
<div class="step"><div class="step-num">3</div>
<div class="step-text">Click <strong>Save</strong>. Your credentials will be
validated against the QNAP before saving.</div></div>
<div class="step"><div class="step-num">4</div>
<div class="step-text">Configure your MCP client with the connection details
shown below the form.</div></div>
</div>"""

    reset_btn = ""
    if has_config:
        reset_btn = '<a href="/reset" class="btn btn-danger">Reset</a>'

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MCP QVS Server — Setup</title>
<style>{CSS}</style></head>
<body><div class="container">
<h1>MCP QVS Server</h1>
<p class="subtitle">Manage QNAP Virtualization Station VMs with AI</p>
{msg_html}
{setup_steps}
<form method="POST" action="/validate">
<div class="card">
<h2 style="color: #58a6ff; font-size: 16px; margin-bottom: 16px;">
QNAP Connection</h2>
{rows}
</div>
<div class="actions">
{reset_btn}
<button type="submit" class="btn btn-primary">Save</button>
</div>
</form>
<div class="setup-info" style="margin-top: 24px;">
<h2>MCP Client Configuration</h2>
<p>Add this to your Claude Code (<code>~/.claude.json</code>) or
Claude Desktop config:</p>
<div class="copy-block">
<button type="button" class="btn btn-sm" onclick="copyConfig()">Copy</button>
<div class="client-config" id="clientConfig"></div></div></div>
<div class="setup-info"><h2>Need Help?</h2><p>
<a href="https://github.com/arnstarn/mcp-server-qnap-qvs"
style="color: #58a6ff;" target="_blank">GitHub Repository</a> —
documentation, troubleshooting, and source code.</p></div>
</div>
<script>{JS_MAIN}</script>
</body></html>"""


def render_review(values: dict[str, str], valid: bool, msg: str) -> str:
    """Render the review/confirmation page after validation."""
    rows = ""
    for key, label, default, _ in FIELDS:
        val = values.get(key, default)
        display = "••••••••" if "PASSWORD" in key else html.escape(val)
        css = ' class="masked"' if "PASSWORD" in key else ""
        rows += f"<tr><td>{html.escape(label)}</td><td{css}>{display}</td></tr>"

    if valid:
        status_class = "message-success"
        status_icon = "Connected successfully"
        buttons = f"""
        <div class="actions">
            <a href="/" class="btn">Edit Settings</a>
            <form method="POST" action="/confirm" style="display:inline">
                {"".join(
                    f'<input type="hidden" name="{k}" value="{html.escape(v)}">'
                    for k, v in values.items()
                )}
                <button type="submit" class="btn btn-primary">
                    Confirm &amp; Restart Server</button>
            </form>
        </div>"""
    else:
        status_class = "message-error"
        status_icon = "Connection failed"
        buttons = """
        <div class="actions">
            <a href="/" class="btn btn-primary">Go Back &amp; Fix</a>
        </div>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MCP QVS Server — Review Settings</title>
<style>{CSS}</style></head>
<body><div class="container">
<h1>MCP QVS Server</h1>
<p class="subtitle">Review your settings</p>
<div class="message {status_class}">{status_icon}: {html.escape(msg)}</div>
<div class="card">
<h2 style="color: #58a6ff; font-size: 16px; margin-bottom: 16px;">
Settings Summary</h2>
<table class="review-table">{rows}</table>
</div>
{buttons}
</div></body></html>"""


def render_success(values: dict[str, str]) -> str:
    """Render the success page after saving and restarting."""
    token = html.escape(values.get("MCP_AUTH_TOKEN", ""))

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MCP QVS Server — Saved</title>
<style>{CSS}</style></head>
<body><div class="container">
<h1>MCP QVS Server</h1>
<p class="subtitle">Setup complete</p>
<div class="message message-success">
Settings saved. The MCP server is restarting with your new configuration.
</div>
<div class="card">
<h2 style="color: #58a6ff; font-size: 16px; margin-bottom: 16px;">
What's Next</h2>
<div class="step"><div class="step-num">1</div>
<div class="step-text">The MCP server will be ready in a few seconds on
port <strong>8445</strong>.</div></div>
<div class="step"><div class="step-num">2</div>
<div class="step-text">Copy the client configuration below into your
MCP client (Claude Code, Claude Desktop, etc.).</div></div>
<div class="step"><div class="step-num">3</div>
<div class="step-text">You can return to this page anytime to update
your settings.</div></div>
</div>
<div class="setup-info">
<h2>MCP Client Configuration</h2>
<p>Add this to <code>~/.claude.json</code> or your MCP client config:</p>
<div class="copy-block">
<button type="button" class="btn btn-sm" onclick="copyConfig()">Copy</button>
<div class="client-config" id="clientConfig"></div></div></div>
</div>
<script>
function copyConfig() {{
    navigator.clipboard.writeText(
        document.getElementById('clientConfig').textContent);
}}
const host = window.location.hostname;
const config = JSON.stringify({{
    mcpServers: {{ "qnap-qvs": {{
        url: "http://" + host + ":8445/sse",
        headers: {{ Authorization: "Bearer {token}" }},
        transportType: "sse"
    }}}}
}}, null, 2);
document.getElementById('clientConfig').textContent = config;
</script>
</body></html>"""


class ConfigHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/api/config":
            values = read_env()
            self._json_response(values)
            return
        if self.path == "/api/generate-token":
            self._json_response({"token": secrets.token_urlsafe(48)})
            return
        if self.path == "/reset":
            try:
                os.remove(ENV_FILE)
            except FileNotFoundError:
                pass
            defaults: dict[str, str] = {}
            self._html_response(render_form(
                defaults, "Configuration reset. Enter new values below.", "info"
            ))
            return
        values = read_env()
        self._html_response(render_form(values))

    def do_POST(self) -> None:
        values = self._parse_form()

        if self.path == "/validate":
            valid, msg = validate_connection(values)
            self._html_response(render_review(values, valid, msg))

        elif self.path == "/confirm":
            write_env(values)
            self._html_response(render_success(values))
            # Schedule a delayed restart so the response page renders
            threading.Thread(
                target=self._delayed_restart, daemon=True
            ).start()

        else:
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()

    def _parse_form(self) -> dict[str, str]:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode()
        params = urllib.parse.parse_qs(body)
        return {k: v[0] for k, v in params.items()}

    def _html_response(self, body: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode())

    def _json_response(self, data: dict) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    @staticmethod
    def _delayed_restart() -> None:
        """Wait for the response to be sent, then restart."""
        time.sleep(3)
        os.system("kill 1 2>/dev/null")

    def log_message(self, format: str, *args: object) -> None:
        pass


def main() -> None:
    with socketserver.TCPServer(("0.0.0.0", UI_PORT), ConfigHandler) as httpd:
        print(f"Config UI running on http://0.0.0.0:{UI_PORT}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
