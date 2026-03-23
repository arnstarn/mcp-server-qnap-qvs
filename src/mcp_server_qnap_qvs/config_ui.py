"""Web UI for configuring and monitoring the MCP QVS server.

Features:
- Dashboard with service status, connection health, and resource overview
- Settings form with QNAP credential management and MCP auth token
- Connection test (validates QNAP API connectivity without saving)
- Log viewer (tails the MCP server log file)
- First-run setup wizard for new installations
- Password-protected access with change password support
- Auto-detects QNAP hostname from browser URL

Runs on port 8446 (CONFIG_UI_PORT). Binds to CONFIG_UI_HOST (default 127.0.0.1).
"""

from __future__ import annotations

import collections
import hashlib
import html
import http.cookies
import http.server
import json
import os
import secrets
import socket
import socketserver
import ssl
import threading
import time
import urllib.parse
import urllib.request

try:
    from . import __version__
    VERSION = __version__.__version__
except Exception:
    VERSION = "unknown"

ENV_FILE = os.environ.get("ENV_FILE", "/config/.env")
LOG_FILE = os.environ.get("LOG_FILE", "/config/mcp-qvs.log")
UI_PORT = int(os.environ.get("CONFIG_UI_PORT", "8446"))
UI_HOST = os.environ.get("CONFIG_UI_HOST", "127.0.0.1")
UI_PASSWORD_FILE = os.environ.get("CONFIG_UI_PASSWORD_FILE", "/config/.ui_password")
MCP_PORT = int(os.environ.get("MCP_PORT", "8445"))
SESSION_SECRET = secrets.token_hex(32)
START_TIME = time.time()

FIELDS = [
    ("QNAP_HOST", "QNAP Hostname / IP", "",
     "Hostname or IP of your QNAP NAS. Auto-detected from your browser."),
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

# ── CSS ──────────────────────────────────────────────────────────

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
background:#0d1117;color:#e6edf3;padding:0}
.container{max-width:720px;margin:0 auto;padding:20px}
h1{color:#58a6ff;margin-bottom:4px;font-size:22px}
.subtitle{color:#8b949e;margin-bottom:16px;font-size:13px}
.nav{background:#161b22;border-bottom:1px solid #30363d;padding:0 20px;
display:flex;align-items:center;gap:0;overflow-x:auto}
.nav a{color:#8b949e;text-decoration:none;padding:12px 16px;font-size:13px;
white-space:nowrap;border-bottom:2px solid transparent}
.nav a:hover{color:#e6edf3}
.nav a.active{color:#58a6ff;border-bottom-color:#58a6ff}
.nav .spacer{flex:1}
.nav .ver{color:#484f58;font-size:11px;padding:12px 16px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;
padding:20px;margin-bottom:16px}
.card h2{color:#58a6ff;font-size:15px;margin-bottom:12px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media(max-width:600px){.grid{grid-template-columns:1fr}}
.stat{text-align:center;padding:16px}
.stat .num{font-size:28px;font-weight:700;color:#e6edf3}
.stat .lbl{font-size:11px;color:#8b949e;margin-top:4px}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;
margin-right:6px;vertical-align:middle}
.dot-green{background:#3fb950}.dot-red{background:#f85149}
.dot-yellow{background:#d29922}
.field{margin-bottom:16px}
label{display:block;font-weight:600;margin-bottom:4px;font-size:13px}
.hint{color:#8b949e;font-size:11px;margin-top:3px}
.input{width:100%;padding:8px 12px;background:#0d1117;border:1px solid #30363d;
border-radius:6px;color:#e6edf3;font-size:13px}
.input:focus{border-color:#58a6ff;outline:none}
select.input{appearance:auto}
.input-row{display:flex;gap:6px;align-items:center}
.input-row .input{flex:1}
.btn{padding:7px 14px;border-radius:6px;border:1px solid #30363d;
background:#21262d;color:#e6edf3;cursor:pointer;font-size:12px;
white-space:nowrap;text-decoration:none;display:inline-block}
.btn:hover{background:#30363d}
.btn-primary{background:#238636;border-color:#238636}
.btn-primary:hover{background:#2ea043}
.btn-danger{background:#da3633;border-color:#da3633}
.btn-danger:hover{background:#f85149}
.btn-sm{padding:3px 10px;font-size:11px}
.actions{display:flex;gap:10px;justify-content:flex-end;margin-top:16px}
.msg{border-radius:6px;padding:10px 14px;margin-bottom:12px;font-size:13px}
.msg-info{background:#1f6feb22;border:1px solid #1f6feb;color:#58a6ff}
.msg-ok{background:#23863622;border:1px solid #238636;color:#3fb950}
.msg-err{background:#da363322;border:1px solid #da3633;color:#f85149}
.step{display:flex;gap:10px;margin-bottom:12px}
.step-n{background:#238636;color:#fff;width:22px;height:22px;border-radius:50%;
display:flex;align-items:center;justify-content:center;font-size:11px;
font-weight:700;flex-shrink:0}
.step-t{color:#c9d1d9;font-size:12px;line-height:1.5}
pre.log{background:#0d1117;border:1px solid #30363d;border-radius:6px;
padding:12px;font-size:11px;color:#8b949e;overflow-x:auto;
max-height:500px;overflow-y:auto;white-space:pre-wrap;word-break:break-all}
.mono{font-family:monospace;background:#0d1117;border:1px solid #30363d;
border-radius:6px;padding:12px;font-size:11px;color:#e6edf3;
white-space:pre;overflow-x:auto}
.copy-block{position:relative}
.copy-block button{position:absolute;top:6px;right:6px}
.tbl{width:100%;border-collapse:collapse}
.tbl td{padding:6px 10px;border-bottom:1px solid #21262d;font-size:12px;
vertical-align:top}
.tbl td:first-child{color:#8b949e;width:150px;font-weight:600}
.masked{color:#484f58}
.footer{color:#484f58;font-size:10px;text-align:center;margin-top:24px;
padding:12px}
.footer a{color:#484f58}
"""

# ── Helpers ──────────────────────────────────────────────────────


def _hash_pw(pw: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}:{pw}".encode()).hexdigest()
    return f"{salt}:{h}"


def _verify_pw(pw: str, stored: str) -> bool:
    if ":" not in stored:
        return False
    salt, expected = stored.split(":", 1)
    return hashlib.sha256(f"{salt}:{pw}".encode()).hexdigest() == expected


def _has_pw() -> bool:
    return os.path.exists(UI_PASSWORD_FILE)


def _save_pw(pw: str) -> None:
    with open(UI_PASSWORD_FILE, "w") as f:
        f.write(_hash_pw(pw))


def _check_pw(pw: str) -> bool:
    try:
        with open(UI_PASSWORD_FILE) as f:
            return _verify_pw(pw, f.read().strip())
    except FileNotFoundError:
        return False


def _session_token(pw_hash: str) -> str:
    return hashlib.sha256(f"{SESSION_SECRET}:{pw_hash}".encode()).hexdigest()[:32]


def _valid_session(cookie_hdr: str) -> bool:
    if not _has_pw():
        return True
    try:
        c = http.cookies.SimpleCookie(cookie_hdr)
        tok = c.get("mcp_qvs_session")
        if not tok:
            return False
        with open(UI_PASSWORD_FILE) as f:
            return tok.value == _session_token(f.read().strip())
    except Exception:
        return False


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


def _check_port(port: int) -> bool:
    """Check if a local port is responding."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except Exception:
        return False


def _test_qnap(values: dict[str, str]) -> tuple[bool, str]:
    """Test QNAP API connectivity."""
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
            if "<authPassed><![CDATA[1]]>" in body:
                return True, "Connected successfully."
            return False, "Login failed — check username and password."
    except Exception as e:
        return False, f"Connection failed: {e}"


def _read_log(lines: int = 100) -> str:
    """Read last N lines from the log file."""
    try:
        with open(LOG_FILE) as f:
            return "\n".join(collections.deque(f, maxlen=lines))
    except FileNotFoundError:
        return "(No log file found. The MCP server may not have started yet.)"


def _uptime() -> str:
    secs = int(time.time() - START_TIME)
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m {secs % 60}s"
    hrs = secs // 3600
    mins = (secs % 3600) // 60
    return f"{hrs}h {mins}m"


# ── Page renderers ───────────────────────────────────────────────

def _nav(active: str) -> str:
    items = [
        ("Dashboard", "/"), ("Settings", "/settings"),
        ("Logs", "/logs"), ("Change Password", "/change-password"),
    ]
    links = ""
    for label, href in items:
        cls = ' class="active"' if active == label else ""
        links += f'<a href="{href}"{cls}>{label}</a>'
    return f"""<div class="nav">{links}<div class="spacer"></div>
<span class="ver">v{VERSION}</span>
<a href="/logout">Logout</a></div>"""


def _page(title: str, nav_active: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MCP QVS — {title}</title>
<style>{CSS}</style></head>
<body>{_nav(nav_active)}
<div class="container">{body}</div>
<div class="footer">
<a href="https://github.com/arnstarn/mcp-server-qnap-qvs"
target="_blank">mcp-server-qnap-qvs</a> v{VERSION}
</div></body></html>"""


def render_dashboard() -> str:
    env = read_env()
    mcp_up = _check_port(MCP_PORT)
    qnap_ok, qnap_msg = (False, "Not configured")
    if env.get("QNAP_HOST") and env.get("QNAP_USERNAME"):
        qnap_ok, qnap_msg = _test_qnap(env)

    mcp_dot = "dot-green" if mcp_up else "dot-red"
    mcp_lbl = "Running" if mcp_up else "Stopped"
    qnap_dot = "dot-green" if qnap_ok else "dot-red"
    has_token = bool(env.get("MCP_AUTH_TOKEN"))
    tok_dot = "dot-green" if has_token else "dot-yellow"
    tok_lbl = "Configured" if has_token else "Not set"
    host = html.escape(env.get("QNAP_HOST", "—"))
    user = html.escape(env.get("QNAP_USERNAME", "—"))

    body = f"""
<h1>Dashboard</h1>
<p class="subtitle">MCP QVS Server Status</p>
<div class="grid">
<div class="card stat">
    <div><span class="dot {mcp_dot}"></span>{mcp_lbl}</div>
    <div class="lbl">MCP Server (port {MCP_PORT})</div>
</div>
<div class="card stat">
    <div><span class="dot {qnap_dot}"></span>{html.escape(qnap_msg[:40])}</div>
    <div class="lbl">QNAP QVS API</div>
</div>
<div class="card stat">
    <div><span class="dot {tok_dot}"></span>{tok_lbl}</div>
    <div class="lbl">MCP Auth Token</div>
</div>
<div class="card stat">
    <div class="num">{_uptime()}</div>
    <div class="lbl">Uptime</div>
</div>
</div>
<div class="card">
<h2>Current Configuration</h2>
<table class="tbl">
<tr><td>QNAP Host</td><td>{host}</td></tr>
<tr><td>Username</td><td>{user}</td></tr>
<tr><td>Password</td><td class="masked">{"set" if env.get("QNAP_PASSWORD") else "not set"}</td></tr>
<tr><td>Auth Token</td><td class="masked">{"set" if has_token else "not set"}</td></tr>
<tr><td>SSL Verify</td><td>{env.get("QNAP_VERIFY_SSL", "false")}</td></tr>
<tr><td>Version</td><td>{VERSION}</td></tr>
</table>
<div class="actions">
<a href="/settings" class="btn btn-primary">Edit Settings</a>
</div>
</div>"""
    return _page("Dashboard", "Dashboard", body)


def render_settings(values: dict[str, str], msg: str = "", mt: str = "info") -> str:
    has_cfg = bool(values.get("QNAP_USERNAME") and values.get("QNAP_PASSWORD"))
    rows = ""
    for key, label, default, hint in FIELDS:
        val = html.escape(values.get(key, default))
        extra = ""
        if key == "MCP_AUTH_TOKEN":
            extra = (
                '<button type="button" class="btn btn-sm" '
                'onclick="generateToken()">Generate</button>'
                '<button type="button" class="btn btn-sm" '
                'onclick="copyToken()">Copy</button>'
            )
        if "PASSWORD" in key or key == "MCP_AUTH_TOKEN":
            sid = f"show_{key}"
            inp = (
                f'<input type="password" name="{key}" value="{val}" '
                f'class="input" id="field_{key}">'
                f'<button type="button" class="btn btn-sm" id="{sid}" '
                f"onclick=\"toggleVis('{key}','{sid}')\">Show</button>"
            )
        elif key == "QNAP_VERIFY_SSL":
            sf = "selected" if val != "true" else ""
            st = "selected" if val == "true" else ""
            inp = (
                f'<select name="{key}" class="input">'
                f'<option value="false" {sf}>false (self-signed, typical)</option>'
                f'<option value="true" {st}>true (valid TLS cert)</option>'
                "</select>"
            )
        else:
            inp = (
                f'<input type="text" name="{key}" value="{val}" '
                f'class="input" id="field_{key}">'
            )
        rows += f"""<div class="field"><label>{html.escape(label)}</label>
<div class="input-row">{inp}{extra}</div>
<div class="hint">{html.escape(hint)}</div></div>"""

    msg_html = ""
    if msg:
        msg_html = f'<div class="msg msg-{mt}">{html.escape(msg)}</div>'
    elif has_cfg:
        msg_html = ('<div class="msg msg-ok">Configuration loaded. '
                    "Update fields and Save, or Reset to start fresh.</div>")

    reset = '<a href="/reset" class="btn btn-danger">Reset</a>' if has_cfg else ""
    test_btn = ('<button type="button" class="btn" '
                'onclick="testConnection()">Test Connection</button>')

    body = f"""
<h1>Settings</h1>
<p class="subtitle">QNAP credentials and MCP auth token</p>
{msg_html}
<div id="testResult"></div>
<form method="POST" action="/validate">
<div class="card">
<h2>QNAP Connection</h2>
{rows}
</div>
<div class="actions">{reset}{test_btn}
<button type="submit" class="btn btn-primary">Save</button>
</div></form>
<div class="card" style="margin-top:16px">
<h2>MCP Client Configuration</h2>
<p class="hint" style="margin-bottom:8px">
Add this to <code>~/.claude.json</code> or your MCP client config:</p>
<div class="copy-block">
<button type="button" class="btn btn-sm" onclick="copyConfig()">Copy</button>
<div class="mono" id="clientConfig"></div></div></div>
<script>
function toggleVis(fid,bid){{
var f=document.getElementById('field_'+fid),b=document.getElementById(bid);
if(f.type==='password'){{f.type='text';b.textContent='Hide'}}
else{{f.type='password';b.textContent='Show'}}
}}
function generateToken(){{
var c='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_',t='';
var a=new Uint8Array(48);crypto.getRandomValues(a);
a.forEach(function(b){{t+=c[b%c.length]}});
document.getElementById('field_MCP_AUTH_TOKEN').value=t;updateCC()}}
function copyToken(){{
var f=document.getElementById('field_MCP_AUTH_TOKEN');
navigator.clipboard.writeText(f.value).then(function(){{f.select()}})}}
function copyConfig(){{
navigator.clipboard.writeText(document.getElementById('clientConfig').textContent)}}
function updateCC(){{
var t=document.getElementById('field_MCP_AUTH_TOKEN').value||'your-token';
var h=window.location.hostname;
var c=JSON.stringify({{mcpServers:{{"qnap-qvs":{{
url:"http://"+h+":{MCP_PORT}/sse",
headers:{{Authorization:"Bearer "+t}},transportType:"sse"}}}}}},null,2);
document.getElementById('clientConfig').textContent=c}}
function testConnection(){{
var r=document.getElementById('testResult');
r.innerHTML='<div class="msg msg-info">Testing connection...</div>';
var fd=new FormData(document.querySelector('form'));
var p=new URLSearchParams(fd).toString();
fetch('/api/test-connection',{{method:'POST',
headers:{{'Content-Type':'application/x-www-form-urlencoded'}},body:p}})
.then(function(x){{return x.json()}}).then(function(d){{
var cls=d.ok?'msg-ok':'msg-err';
r.innerHTML='<div class="msg '+cls+'">'+d.message+'</div>'}})
.catch(function(e){{r.innerHTML='<div class="msg msg-err">'+e+'</div>'}})}}
document.querySelectorAll('input').forEach(function(e){{
e.addEventListener('input',updateCC)}});
(function(){{var f=document.getElementById('field_QNAP_HOST');
if(f&&(!f.value||f.value==='localhost')){{
var h=window.location.hostname;
if(h&&h!=='localhost'&&h!=='127.0.0.1'){{f.value=h}}}}
}})();
updateCC();
</script>"""
    return _page("Settings", "Settings", body)


def render_review(values: dict[str, str], ok: bool, msg: str) -> str:
    rows = ""
    for key, label, default, _ in FIELDS:
        val = values.get(key, default)
        disp = "set" if ("PASSWORD" in key or key == "MCP_AUTH_TOKEN") else html.escape(val)
        css = ' class="masked"' if ("PASSWORD" in key or key == "MCP_AUTH_TOKEN") else ""
        rows += f"<tr><td>{html.escape(label)}</td><td{css}>{disp}</td></tr>"

    if ok:
        hidden = "".join(
            f'<input type="hidden" name="{k}" value="{html.escape(v)}">'
            for k, v in values.items()
        )
        buttons = f"""<div class="actions">
<a href="/settings" class="btn">Edit</a>
<form method="POST" action="/confirm" style="display:inline">
{hidden}
<button type="submit" class="btn btn-primary">Confirm &amp; Restart</button>
</form></div>"""
        mc = "msg-ok"
    else:
        buttons = '<div class="actions"><a href="/settings" class="btn btn-primary">Go Back</a></div>'
        mc = "msg-err"

    body = f"""
<h1>Review Settings</h1>
<div class="msg {mc}">{html.escape(msg)}</div>
<div class="card"><h2>Summary</h2>
<table class="tbl">{rows}</table></div>
{buttons}"""
    return _page("Review", "Settings", body)


def render_success(values: dict[str, str]) -> str:
    token = html.escape(values.get("MCP_AUTH_TOKEN", ""))
    body = f"""
<h1>Setup Complete</h1>
<div class="msg msg-ok">Settings saved. The MCP server is restarting.</div>
<div class="card"><h2>What's Next</h2>
<div class="step"><div class="step-n">1</div>
<div class="step-t">The MCP server will be ready in a few seconds on port
<strong>{MCP_PORT}</strong>.</div></div>
<div class="step"><div class="step-n">2</div>
<div class="step-t">Copy the client configuration below into your MCP
client.</div></div></div>
<div class="card"><h2>MCP Client Configuration</h2>
<div class="copy-block">
<button type="button" class="btn btn-sm" onclick="copyConfig()">Copy</button>
<div class="mono" id="clientConfig"></div></div></div>
<script>
function copyConfig(){{
navigator.clipboard.writeText(document.getElementById('clientConfig').textContent)}}
var h=window.location.hostname;
document.getElementById('clientConfig').textContent=JSON.stringify({{
mcpServers:{{"qnap-qvs":{{url:"http://"+h+":{MCP_PORT}/sse",
headers:{{Authorization:"Bearer {token}"}},transportType:"sse"}}}}}},null,2);
</script>"""
    return _page("Complete", "Settings", body)


def render_logs() -> str:
    log = html.escape(_read_log(200))
    body = f"""
<h1>Server Logs</h1>
<p class="subtitle">Last 200 lines from the MCP server</p>
<div class="actions" style="margin-bottom:12px">
<button class="btn btn-sm" onclick="location.reload()">Refresh</button></div>
<pre class="log">{log}</pre>"""
    return _page("Logs", "Logs", body)


def render_login(msg: str = "", setup: bool = False) -> str:
    title = "Set Config UI Password" if setup else "Login"
    btn = "Set Password" if setup else "Login"
    info = ("Choose a password to protect this page (min 6 characters)."
            if setup else "Enter your config UI password.")
    extra = ""
    if setup:
        extra = """<div class="field"><label>Confirm Password</label>
<input type="password" name="confirm" class="input" required
placeholder="Confirm password"></div>"""
    msg_html = f'<div class="msg msg-err">{html.escape(msg)}</div>' if msg else ""
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MCP QVS — {title}</title><style>{CSS}</style></head>
<body><div class="container" style="max-width:400px;margin-top:60px">
<h1 style="text-align:center">MCP QVS Server</h1>
<p class="subtitle" style="text-align:center">{title}</p>
{msg_html}
<div class="card"><p class="hint" style="margin-bottom:12px">{info}</p>
<form method="POST" action="/login">
<div class="field"><label>Password</label>
<input type="password" name="password" class="input" required autofocus></div>
{extra}
<div class="actions"><button type="submit" class="btn btn-primary">{btn}</button>
</div></form></div>
<div class="footer">
<a href="https://github.com/arnstarn/mcp-server-qnap-qvs"
target="_blank">mcp-server-qnap-qvs</a> v{VERSION}</div>
</div></body></html>"""


def render_change_pw(msg: str = "", mt: str = "info") -> str:
    msg_html = f'<div class="msg msg-{mt}">{html.escape(msg)}</div>' if msg else ""
    body = f"""
<h1>Change Password</h1>
{msg_html}
<div class="card">
<form method="POST" action="/change-password">
<div class="field"><label>Current Password</label>
<input type="password" name="current" class="input" required></div>
<div class="field"><label>New Password</label>
<input type="password" name="password" class="input" required
placeholder="Min 6 characters"></div>
<div class="field"><label>Confirm New Password</label>
<input type="password" name="confirm" class="input" required></div>
<div class="actions"><a href="/" class="btn">Cancel</a>
<button type="submit" class="btn btn-primary">Change Password</button>
</div></form></div>
<p class="hint" style="margin-top:12px">
Forgot your password? SSH into the NAS and run:<br>
<code style="font-size:10px">rm $(getcfg mcp-server-qnap-qvs Install_Path
-f /etc/config/qpkg.conf)/.ui_password</code></p>"""
    return _page("Change Password", "Change Password", body)


def render_wizard(step: int = 1, values: dict | None = None,
                  msg: str = "", mt: str = "info") -> str:
    values = values or {}
    msg_html = f'<div class="msg msg-{mt}">{html.escape(msg)}</div>' if msg else ""

    if step == 1:
        host_val = html.escape(values.get("QNAP_HOST", ""))
        port_val = html.escape(values.get("QNAP_PORT", "443"))
        user_val = html.escape(values.get("QNAP_USERNAME", ""))
        pw_val = html.escape(values.get("QNAP_PASSWORD", ""))
        ssl_val = values.get("QNAP_VERIFY_SSL", "false")
        sf = "selected" if ssl_val != "true" else ""
        st = "selected" if ssl_val == "true" else ""
        content = f"""
{msg_html}
<div class="card"><h2>Step 1: QNAP Connection</h2>
<p class="hint" style="margin-bottom:12px">Enter the credentials you use
to log into the QNAP web UI.</p>
<form method="POST" action="/wizard/1">
<div class="field"><label>QNAP Host</label>
<input type="text" name="QNAP_HOST" value="{host_val}" class="input"
id="field_QNAP_HOST" placeholder="e.g. 192.168.1.100"></div>
<div class="field"><label>HTTPS Port</label>
<input type="text" name="QNAP_PORT" value="{port_val}" class="input"></div>
<div class="field"><label>Username</label>
<input type="text" name="QNAP_USERNAME" value="{user_val}" class="input"></div>
<div class="field"><label>Password</label>
<input type="password" name="QNAP_PASSWORD" value="{pw_val}" class="input"></div>
<div class="field"><label>Verify SSL</label>
<select name="QNAP_VERIFY_SSL" class="input">
<option value="false" {sf}>false (self-signed, typical)</option>
<option value="true" {st}>true</option></select></div>
<div class="actions">
<button type="submit" class="btn btn-primary">Test &amp; Continue</button>
</div></form></div>
<script>
(function(){{var f=document.getElementById('field_QNAP_HOST');
if(f&&!f.value){{var h=window.location.hostname;
if(h&&h!=='localhost'&&h!=='127.0.0.1')f.value=h;}}
}})();
</script>"""
    elif step == 2:
        token_val = html.escape(values.get("MCP_AUTH_TOKEN", ""))
        hidden = "".join(
            f'<input type="hidden" name="{k}" value="{html.escape(v)}">'
            for k, v in values.items() if k != "MCP_AUTH_TOKEN"
        )
        content = f"""
{msg_html}
<div class="card"><h2>Step 2: MCP Auth Token</h2>
<p class="hint" style="margin-bottom:12px">
This token is a shared secret between the MCP server and your AI client.
Click Generate to create one.</p>
<form method="POST" action="/wizard/2">
{hidden}
<div class="field"><label>Auth Token</label>
<div class="input-row">
<input type="text" name="MCP_AUTH_TOKEN" value="{token_val}"
class="input" id="field_MCP_AUTH_TOKEN">
<button type="button" class="btn btn-sm"
onclick="generateToken()">Generate</button>
<button type="button" class="btn btn-sm"
onclick="copyToken()">Copy</button>
</div></div>
<div class="actions">
<button type="submit" class="btn btn-primary">Save &amp; Finish</button>
</div></form></div>
<script>
function generateToken(){{
var c='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_',t='';
var a=new Uint8Array(48);crypto.getRandomValues(a);
a.forEach(function(b){{t+=c[b%c.length]}});
document.getElementById('field_MCP_AUTH_TOKEN').value=t}}
function copyToken(){{
var f=document.getElementById('field_MCP_AUTH_TOKEN');
navigator.clipboard.writeText(f.value).then(function(){{f.select()}})}}
</script>"""
    else:
        content = ""

    steps_bar = f"""
<div style="display:flex;gap:8px;margin-bottom:16px">
<div class="step-n" style="{'background:#238636' if step>=1 else 'background:#30363d'}">1</div>
<div style="flex:1;height:2px;background:{'#238636' if step>=2 else '#30363d'};align-self:center"></div>
<div class="step-n" style="{'background:#238636' if step>=2 else 'background:#30363d'}">2</div>
</div>"""

    body = f"""
<h1>Setup Wizard</h1>
<p class="subtitle">First-time configuration</p>
{steps_bar}
{content}"""
    return _page("Setup", "", body)


# ── Request Handler ──────────────────────────────────────────────

class Handler(http.server.BaseHTTPRequestHandler):
    def _auth_ok(self) -> bool:
        if _valid_session(self.headers.get("Cookie", "")):
            return True
        if not _has_pw():
            self._html(render_login(setup=True))
        else:
            self._html(render_login())
        return False

    def do_GET(self) -> None:
        p = self.path.split("?")[0]

        if p == "/login":
            self._html(render_login(setup=not _has_pw()))
            return

        if not self._auth_ok():
            return

        env = read_env()
        is_first_run = not env.get("QNAP_USERNAME")

        if p == "/" or p == "":
            if is_first_run:
                self._html(render_wizard(1))
            else:
                self._html(render_dashboard())
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
            self.send_header("Set-Cookie",
                             "mcp_qvs_session=; Max-Age=0; Path=/; HttpOnly")
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
            pw = form.get("password", "")
            if not _has_pw():
                confirm = form.get("confirm", "")
                if len(pw) < 6:
                    self._html(render_login("Password must be at least 6 characters.", setup=True))
                    return
                if pw != confirm:
                    self._html(render_login("Passwords do not match.", setup=True))
                    return
                _save_pw(pw)
            elif not _check_pw(pw):
                self._html(render_login("Incorrect password."))
                return
            with open(UI_PASSWORD_FILE) as f:
                tok = _session_token(f.read().strip())
            self.send_response(302)
            self.send_header("Location", "/")
            self.send_header("Set-Cookie",
                             f"mcp_qvs_session={tok}; Path=/; HttpOnly; SameSite=Strict")
            self.end_headers()
            return

        if not self._auth_ok():
            return

        if p == "/api/test-connection":
            ok, msg = _test_qnap(form)
            self._json({"ok": ok, "message": msg})

        elif p == "/validate":
            ok, msg = _test_qnap(form)
            self._html(render_review(form, ok, msg))

        elif p == "/confirm":
            write_env(form)
            self._html(render_success(form))
            threading.Thread(target=self._restart, daemon=True).start()

        elif p == "/wizard/1":
            ok, msg = _test_qnap(form)
            if ok:
                self._html(render_wizard(2, form))
            else:
                self._html(render_wizard(1, form, msg, "err"))

        elif p == "/wizard/2":
            if not form.get("MCP_AUTH_TOKEN"):
                self._html(render_wizard(2, form, "Please set an auth token.", "err"))
                return
            write_env(form)
            self._html(render_success(form))
            threading.Thread(target=self._restart, daemon=True).start()

        elif p == "/change-password":
            if not _check_pw(form.get("current", "")):
                self._html(render_change_pw("Current password is incorrect.", "err"))
                return
            new_pw = form.get("password", "")
            if len(new_pw) < 6:
                self._html(render_change_pw("Must be at least 6 characters.", "err"))
                return
            if new_pw != form.get("confirm", ""):
                self._html(render_change_pw("Passwords do not match.", "err"))
                return
            _save_pw(new_pw)
            with open(UI_PASSWORD_FILE) as f:
                tok = _session_token(f.read().strip())
            self.send_response(302)
            self.send_header("Location", "/")
            self.send_header("Set-Cookie",
                             f"mcp_qvs_session={tok}; Path=/; HttpOnly; SameSite=Strict")
            self.end_headers()

        else:
            self.send_response(302)
            self.send_header("Location", "/")
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


def main() -> None:
    with socketserver.TCPServer((UI_HOST, UI_PORT), Handler) as s:
        print(f"Config UI v{VERSION} on http://{UI_HOST}:{UI_PORT}")
        if UI_HOST == "127.0.0.1":
            print("  Localhost only. Set CONFIG_UI_HOST=0.0.0.0 for network access.")
        if not _has_pw():
            print("  First visit will prompt for a config UI password.")
        s.serve_forever()


if __name__ == "__main__":
    main()
