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
import urllib.parse

ENV_FILE = os.environ.get("ENV_FILE", "/config/.env")
UI_PORT = int(os.environ.get("CONFIG_UI_PORT", "8446"))

FIELDS = [
    (
        "QNAP_HOST", "QNAP Hostname / IP", "localhost",
        "Hostname or IP of your QNAP NAS. Use 'localhost' if running on the NAS.",
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


def read_env() -> dict[str, str]:
    """Read current .env file into a dict."""
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
    """Write values to .env file."""
    with open(ENV_FILE, "w") as f:
        for key, _, default, _ in FIELDS:
            val = values.get(key, default)
            f.write(f"{key}={val}\n")


def render_page(values: dict[str, str], message: str = "") -> str:
    """Render the config HTML page."""
    rows = ""
    for key, label, default, hint in FIELDS:
        val = html.escape(values.get(key, default))
        input_type = "password" if "PASSWORD" in key else "text"
        extra = ""

        if key == "MCP_AUTH_TOKEN":
            extra = """
            <button type="button" class="btn btn-sm" onclick="generateToken()">Generate</button>
            <button type="button" class="btn btn-sm" onclick="copyToken()">Copy</button>
            """

        if key == "QNAP_VERIFY_SSL":
            checked_false = "selected" if val != "true" else ""
            checked_true = "selected" if val == "true" else ""
            input_html = f"""
            <select name="{key}" class="input">
                <option value="false" {checked_false}>false (self-signed cert, typical)</option>
                <option value="true" {checked_true}>true (valid TLS certificate)</option>
            </select>"""
        else:
            input_html = f'<input type="{input_type}" name="{key}" value="{val}" class="input" id="field_{key}">'

        rows += f"""
        <div class="field">
            <label>{html.escape(label)}</label>
            <div class="input-row">
                {input_html}
                {extra}
            </div>
            <div class="hint">{html.escape(hint)}</div>
        </div>
        """

    msg_html = f'<div class="message">{html.escape(message)}</div>' if message else ""

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>MCP QVS Server — Setup</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                background: #0d1117; color: #e6edf3; padding: 20px; }}
        .container {{ max-width: 640px; margin: 0 auto; }}
        h1 {{ color: #58a6ff; margin-bottom: 8px; font-size: 24px; }}
        .subtitle {{ color: #8b949e; margin-bottom: 24px; font-size: 14px; }}
        .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px;
                 padding: 24px; margin-bottom: 16px; }}
        .field {{ margin-bottom: 20px; }}
        label {{ display: block; font-weight: 600; margin-bottom: 4px; font-size: 14px; }}
        .hint {{ color: #8b949e; font-size: 12px; margin-top: 4px; }}
        .input {{ width: 100%; padding: 8px 12px; background: #0d1117; border: 1px solid #30363d;
                  border-radius: 6px; color: #e6edf3; font-size: 14px; }}
        .input:focus {{ border-color: #58a6ff; outline: none; }}
        select.input {{ appearance: auto; }}
        .input-row {{ display: flex; gap: 8px; align-items: center; }}
        .input-row .input {{ flex: 1; }}
        .btn {{ padding: 8px 16px; border-radius: 6px; border: 1px solid #30363d;
                background: #21262d; color: #e6edf3; cursor: pointer; font-size: 13px;
                white-space: nowrap; }}
        .btn:hover {{ background: #30363d; }}
        .btn-primary {{ background: #238636; border-color: #238636; }}
        .btn-primary:hover {{ background: #2ea043; }}
        .btn-sm {{ padding: 4px 12px; font-size: 12px; }}
        .actions {{ display: flex; gap: 12px; justify-content: flex-end; margin-top: 20px; }}
        .message {{ background: #1f6feb22; border: 1px solid #1f6feb; border-radius: 6px;
                    padding: 12px; margin-bottom: 16px; color: #58a6ff; font-size: 14px; }}
        .setup-info {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px;
                       padding: 20px; margin-bottom: 16px; }}
        .setup-info h2 {{ color: #58a6ff; font-size: 16px; margin-bottom: 12px; }}
        .setup-info p {{ color: #8b949e; font-size: 13px; line-height: 1.6; margin-bottom: 8px; }}
        .setup-info code {{ background: #0d1117; padding: 2px 6px; border-radius: 4px;
                            font-size: 12px; color: #e6edf3; }}
        .step {{ display: flex; gap: 12px; margin-bottom: 12px; }}
        .step-num {{ background: #238636; color: white; width: 24px; height: 24px;
                     border-radius: 50%; display: flex; align-items: center;
                     justify-content: center; font-size: 12px; font-weight: 700;
                     flex-shrink: 0; }}
        .step-text {{ color: #c9d1d9; font-size: 13px; line-height: 1.5; }}
        .client-config {{ background: #0d1117; border: 1px solid #30363d; border-radius: 6px;
                          padding: 12px; margin-top: 12px; font-family: monospace;
                          font-size: 12px; color: #e6edf3; white-space: pre; overflow-x: auto; }}
        .copy-block {{ position: relative; }}
        .copy-block button {{ position: absolute; top: 8px; right: 8px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>MCP QVS Server</h1>
        <p class="subtitle">Manage QNAP Virtualization Station VMs with AI</p>

        {msg_html}

        <div class="setup-info">
            <h2>How It Works</h2>
            <div class="step">
                <div class="step-num">1</div>
                <div class="step-text">Enter your QNAP admin credentials below. These are the same
                    username and password you use to log into your QNAP web UI.</div>
            </div>
            <div class="step">
                <div class="step-num">2</div>
                <div class="step-text">Set an MCP Auth Token — this is a secret that your AI client
                    (Claude, etc.) will use to connect. Click <strong>Generate</strong> to create a
                    random one, or type your own.</div>
            </div>
            <div class="step">
                <div class="step-num">3</div>
                <div class="step-text">Click <strong>Save & Restart</strong>. The MCP server will
                    restart with your new settings.</div>
            </div>
            <div class="step">
                <div class="step-num">4</div>
                <div class="step-text">Configure your MCP client with the connection details shown
                    below the form. Use the token you set in step 2.</div>
            </div>
        </div>

        <form method="POST" action="/save">
            <div class="card">
                <h2 style="color: #58a6ff; font-size: 16px; margin-bottom: 16px;">
                    QNAP Connection</h2>
                {rows}
            </div>
            <div class="actions">
                <button type="submit" class="btn btn-primary">Save &amp; Restart</button>
            </div>
        </form>

        <div class="setup-info" style="margin-top: 24px;">
            <h2>MCP Client Configuration</h2>
            <p>Add this to your Claude Code (<code>~/.claude.json</code>) or
               Claude Desktop config:</p>
            <div class="copy-block">
                <button type="button" class="btn btn-sm"
                    onclick="copyConfig()">Copy</button>
                <div class="client-config" id="clientConfig"></div>
            </div>
        </div>

        <div class="setup-info">
            <h2>Need Help?</h2>
            <p>
                <a href="https://github.com/arnstarn/mcp-server-qnap-qvs" style="color: #58a6ff;"
                   target="_blank">GitHub Repository</a> —
                Full documentation, troubleshooting, and source code.
            </p>
        </div>
    </div>

    <script>
        function generateToken() {{
            const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
            let token = '';
            const arr = new Uint8Array(48);
            crypto.getRandomValues(arr);
            arr.forEach(b => token += chars[b % chars.length]);
            document.getElementById('field_MCP_AUTH_TOKEN').value = token;
            updateClientConfig();
        }}

        function copyToken() {{
            const field = document.getElementById('field_MCP_AUTH_TOKEN');
            navigator.clipboard.writeText(field.value).then(() => {{
                field.select();
            }});
        }}

        function copyConfig() {{
            const config = document.getElementById('clientConfig').textContent;
            navigator.clipboard.writeText(config);
        }}

        function updateClientConfig() {{
            const token = document.getElementById('field_MCP_AUTH_TOKEN').value || 'your-token-here';
            const host = window.location.hostname;
            const config = JSON.stringify({{
                mcpServers: {{
                    "qnap-qvs": {{
                        url: `http://${{host}}:8445/sse`,
                        headers: {{
                            Authorization: `Bearer ${{token}}`
                        }},
                        transportType: "sse"
                    }}
                }}
            }}, null, 2);
            document.getElementById('clientConfig').textContent = config;
        }}

        // Update config on any field change
        document.querySelectorAll('input').forEach(el => {{
            el.addEventListener('input', updateClientConfig);
        }});
        updateClientConfig();
    </script>
</body>
</html>"""


class ConfigHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/api/config":
            values = read_env()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(values).encode())
            return

        if self.path == "/api/generate-token":
            token = secrets.token_urlsafe(48)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"token": token}).encode())
            return

        values = read_env()
        page = render_page(values)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(page.encode())

    def do_POST(self) -> None:
        if self.path == "/save":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode()
            params = urllib.parse.parse_qs(body)
            values = {k: v[0] for k, v in params.items()}
            write_env(values)

            # Restart the MCP server container
            os.system("kill 1 2>/dev/null")  # Signal the container to restart

            page = render_page(values, message="Settings saved. MCP server is restarting...")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(page.encode())
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        pass  # Suppress request logs


def main() -> None:
    with socketserver.TCPServer(("0.0.0.0", UI_PORT), ConfigHandler) as httpd:
        print(f"Config UI running on http://0.0.0.0:{UI_PORT}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
