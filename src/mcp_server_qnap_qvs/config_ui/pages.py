"""Page renderers for the config UI."""

from __future__ import annotations

import html

from .constants import FIELDS, MCP_PORT, REGISTRY_FIELDS, VERSION
from .helpers import check_port, read_env, read_log, test_qnap, uptime
from .styles import CSS


def _nav(active: str, user: str = "") -> str:
    items = [
        ("Dashboard", "/"), ("Settings", "/settings"), ("Logs", "/logs"),
    ]
    links = ""
    for label, href in items:
        cls = ' class="active"' if active == label else ""
        links += f'<a href="{href}"{cls}>{label}</a>'
    user_html = f'<span class="ver">{html.escape(user)}</span>' if user else ""
    return f"""<div class="nav">{links}<div class="spacer"></div>
{user_html}<span class="ver">v{VERSION}</span>
<a href="/logout">Logout</a></div>"""


def _page(title: str, nav_active: str, body: str, user: str = "") -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MCP QVS — {title}</title>
<style>{CSS}</style></head>
<body>{_nav(nav_active, user)}
<div class="container">{body}</div>
<div class="footer">
<a href="https://github.com/arnstarn/mcp-server-qnap-qvs"
target="_blank">mcp-server-qnap-qvs</a> v{VERSION}
</div></body></html>"""


def render_dashboard(user: str = "") -> str:
    env = read_env()
    mcp_up = check_port()
    qnap_ok, qnap_msg = (False, "Not configured")
    if env.get("QNAP_HOST") and env.get("QNAP_USERNAME"):
        qnap_ok, qnap_msg = test_qnap(env)

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
    <div class="num">{uptime()}</div>
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
</div></div>
<div class="card">
<h2>Updates</h2>
<div id="updateStatus">
<button type="button" class="btn" onclick="checkUpdate()">Check for Updates</button>
</div>
</div>
<script>
function checkUpdate(){{
var el=document.getElementById('updateStatus');
el.innerHTML='<span class="hint">Checking...</span>';
fetch('/api/check-update').then(function(r){{return r.json()}}).then(function(d){{
if(d.error){{el.innerHTML='<div class="msg msg-err">'+d.error+'</div>';return}}
if(d.update_available){{
el.innerHTML='<div class="msg msg-info">Update available: <strong>v'+d.latest+
'</strong> (current: v'+d.current+')</div>'+
'<div class="actions" style="margin-top:8px">'+
'<a href="'+d.release_url+'" class="btn" target="_blank">Release Notes</a>'+
'<button class="btn btn-primary" onclick="doUpdate()">Update Now</button></div>'
}}else{{
el.innerHTML='<div class="msg msg-ok">You are running the latest version (v'+d.current+')</div>'
}}
}}).catch(function(e){{el.innerHTML='<div class="msg msg-err">'+e+'</div>'}})}}
function doUpdate(){{
var el=document.getElementById('updateStatus');
el.innerHTML='<div class="msg msg-info">Pulling latest image and restarting... this may take a minute.</div>';
fetch('/api/update',{{method:'POST'}}).then(function(r){{return r.json()}}).then(function(d){{
if(d.ok){{
el.innerHTML='<div class="msg msg-ok">'+d.message+' The page will reload shortly.</div>';
setTimeout(function(){{location.reload()}},10000)
}}else{{
el.innerHTML='<div class="msg msg-err">'+d.message+'</div>'
}}
}}).catch(function(e){{el.innerHTML='<div class="msg msg-err">'+e+'</div>'}})}}
</script>"""
    return _page("Dashboard", "Dashboard", body, user)


def render_settings(values: dict[str, str], msg: str = "", mt: str = "info", user: str = "") -> str:
    has_cfg = bool(values.get("QNAP_USERNAME") and values.get("QNAP_PASSWORD"))
    rows = ""
    for key, label, default, hint_text in FIELDS:
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
<div class="hint">{html.escape(hint_text)}</div></div>"""

    msg_html = ""
    if msg:
        msg_html = f'<div class="msg msg-{mt}">{html.escape(msg)}</div>'
    elif has_cfg:
        msg_html = ('<div class="msg msg-ok">Configuration loaded. '
                    "Update fields and Save, or Reset to start fresh.</div>")

    reset = '<a href="/reset" class="btn btn-danger">Reset</a>' if has_cfg else ""
    test_btn = ('<button type="button" class="btn" '
                'onclick="testConnection()">Test Connection</button>')

    # Build registry fields
    reg_rows = ""
    for key, label, default, hint_text in REGISTRY_FIELDS:
        val = html.escape(values.get(key, default))
        if "PASSWORD" in key:
            sid = f"show_{key}"
            inp = (
                f'<input type="password" name="{key}" value="{val}" '
                f'class="input" id="field_{key}">'
                f'<button type="button" class="btn btn-sm" id="{sid}" '
                f"onclick=\"toggleVis('{key}','{sid}')\">Show</button>"
            )
        else:
            inp = (
                f'<input type="text" name="{key}" value="{val}" '
                f'class="input" id="field_{key}">'
            )
        reg_rows += f"""<div class="field"><label>{html.escape(label)}</label>
<div class="input-row">{inp}</div>
<div class="hint">{html.escape(hint_text)}</div></div>"""

    body = f"""
<h1>Settings</h1>
<p class="subtitle">QNAP credentials and MCP auth token</p>
{msg_html}
<div id="testResult"></div>
<form method="POST" action="/validate">
<div class="card"><h2>QNAP Connection</h2>{rows}</div>
<details class="card" style="cursor:pointer">
<summary><h2 style="display:inline;cursor:pointer">Docker Registry (Optional)</h2>
<span class="hint" style="margin-left:8px">
Only needed if image pulls hit rate limits</span></summary>
<div style="margin-top:12px">{reg_rows}</div>
</details>
<div class="actions">{reset}{test_btn}
<button type="submit" class="btn btn-primary">Save</button>
</div></form>
<div class="card" style="margin-top:16px">
<h2>MCP Client Configuration</h2>
<p class="hint" style="margin-bottom:12px">
Connect any MCP-compatible client. Credentials are hidden by default.</p>
<div style="margin-bottom:12px">
<strong style="font-size:12px">SSE Endpoint:</strong>
<code id="sseEndpoint" style="font-size:11px"></code>
<button type="button" class="btn btn-sm"
onclick="navigator.clipboard.writeText(document.getElementById('sseEndpoint').textContent)">
Copy</button>
</div>
<div style="margin-bottom:16px">
<strong style="font-size:12px">Auth Token:</strong>
<code id="authTokenDisplay" style="font-size:11px">••••••••</code>
<button type="button" class="btn btn-sm"
onclick="navigator.clipboard.writeText(document.getElementById('authTokenReal').value)">
Copy</button>
<input type="hidden" id="authTokenReal">
</div>
<div style="margin-bottom:12px">
<button type="button" class="btn" id="revealBtn" onclick="toggleAllConfigs()">
Reveal All Configs</button>
</div>
<div id="configBlocks" style="display:none">
<div style="margin-bottom:12px">
<strong style="font-size:12px">Claude Code</strong>
<span class="hint">(~/.claude.json)</span>
<button type="button" class="btn btn-sm" style="float:right"
onclick="copyEl('cfgClaude')">Copy</button>
<div class="mono" id="cfgClaude" style="margin-top:4px"></div></div>
<div style="margin-bottom:12px">
<strong style="font-size:12px">Claude Desktop</strong>
<span class="hint">(claude_desktop_config.json)</span>
<button type="button" class="btn btn-sm" style="float:right"
onclick="copyEl('cfgDesktop')">Copy</button>
<div class="mono" id="cfgDesktop" style="margin-top:4px"></div></div>
<div style="margin-bottom:12px">
<strong style="font-size:12px">VS Code / Cursor</strong>
<span class="hint">(.vscode/mcp.json)</span>
<button type="button" class="btn btn-sm" style="float:right"
onclick="copyEl('cfgVscode')">Copy</button>
<div class="mono" id="cfgVscode" style="margin-top:4px"></div></div>
<div style="margin-bottom:12px">
<strong style="font-size:12px">Other MCP Clients</strong>
<div class="mono" id="cfgOther" style="margin-top:4px"></div></div>
</div>
</div>
<div class="card"><h2>Help</h2>
<p style="display:flex;gap:16px;flex-wrap:wrap">
<a href="/logout" style="color:#58a6ff">Logout</a>
<a href="https://github.com/arnstarn/mcp-server-qnap-qvs"
style="color:#58a6ff" target="_blank">GitHub</a></p>
</div>
<script>
function toggleVis(fid,bid){{
var f=document.getElementById('field_'+fid),b=document.getElementById(bid);
if(f.type==='password'){{f.type='text';b.textContent='Hide'}}
else{{f.type='password';b.textContent='Show'}}}}
function generateToken(){{
var c='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_',t='';
var a=new Uint8Array(48);crypto.getRandomValues(a);
a.forEach(function(b){{t+=c[b%c.length]}});
document.getElementById('field_MCP_AUTH_TOKEN').value=t;updateCC()}}
function copyToken(){{var f=document.getElementById('field_MCP_AUTH_TOKEN');
navigator.clipboard.writeText(f.value).then(function(){{f.select()}})}}
function copyEl(id){{navigator.clipboard.writeText(document.getElementById(id).textContent)}}
var _configsVisible=false;
function toggleAllConfigs(){{
var blocks=document.getElementById('configBlocks');
var btn=document.getElementById('revealBtn');
var tokenEl=document.getElementById('authTokenDisplay');
var real=document.getElementById('authTokenReal').value;
_configsVisible=!_configsVisible;
if(_configsVisible){{
blocks.style.display='block';tokenEl.textContent=real;
btn.textContent='Hide All Configs'}}
else{{
blocks.style.display='none';tokenEl.textContent='••••••••';
btn.textContent='Reveal All Configs'}}}}
function updateCC(){{
var t=document.getElementById('field_MCP_AUTH_TOKEN').value||'your-token';
var h=window.location.hostname;
var url="http://"+h+":{MCP_PORT}/sse";
document.getElementById('sseEndpoint').textContent=url;
document.getElementById('authTokenReal').value=t;
if(!_configsVisible)document.getElementById('authTokenDisplay').textContent='••••••••';
var claude=JSON.stringify({{mcpServers:{{"qnap-qvs":{{
url:url,headers:{{Authorization:"Bearer "+t}},transportType:"sse"}}}}}},null,2);
document.getElementById('cfgClaude').textContent=claude;
document.getElementById('cfgDesktop').textContent=claude;
var vscode=JSON.stringify({{servers:{{"qnap-qvs":{{
url:url,headers:{{Authorization:"Bearer "+t}}}}}}}},null,2);
document.getElementById('cfgVscode').textContent=vscode;
document.getElementById('cfgOther').textContent=
"Endpoint: "+url+"\\nTransport: SSE (Server-Sent Events)\\n"+
"Auth Header: Authorization: Bearer "+t}}
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
updateCC();
</script>"""
    return _page("Settings", "Settings", body, user)


def render_review(values: dict[str, str], ok: bool, msg: str, user: str = "") -> str:
    rows = ""
    for key, label, default, _ in FIELDS:
        val = values.get(key, default)
        is_secret = "PASSWORD" in key or key == "MCP_AUTH_TOKEN"
        disp = "set" if is_secret else html.escape(val)
        css = ' class="masked"' if is_secret else ""
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
        buttons = ('<div class="actions">'
                   '<a href="/settings" class="btn btn-primary">Go Back</a></div>')
        mc = "msg-err"

    body = f"""
<h1>Review Settings</h1>
<div class="msg {mc}">{html.escape(msg)}</div>
<div class="card"><h2>Summary</h2>
<table class="tbl">{rows}</table></div>{buttons}"""
    return _page("Review", "Settings", body, user)


def render_success(values: dict[str, str], user: str = "") -> str:
    token = html.escape(values.get("MCP_AUTH_TOKEN", ""))
    body = f"""
<h1>Setup Complete</h1>
<div class="msg msg-ok">Settings saved. The MCP server is restarting.</div>
<div class="card"><h2>What's Next</h2>
<div class="step"><div class="step-n">1</div>
<div class="step-t">The MCP server will be ready in a few seconds on port
<strong>{MCP_PORT}</strong>.</div></div>
<div class="step"><div class="step-n">2</div>
<div class="step-t">Copy the client configuration below.</div></div></div>
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
    return _page("Complete", "Settings", body, user)


def render_logs(user: str = "") -> str:
    log = html.escape(read_log(200))
    body = f"""
<h1>Server Logs</h1>
<p class="subtitle">Last 200 lines from the MCP server</p>
<div class="actions" style="margin-bottom:12px">
<button class="btn btn-sm" onclick="location.reload()">Refresh</button></div>
<pre class="log">{log}</pre>"""
    return _page("Logs", "Logs", body, user)


def render_login(msg: str = "") -> str:
    title = "Login"
    info = "Sign in with your QNAP admin credentials."
    msg_html = (f'<div class="msg msg-err">{html.escape(msg)}</div>'
                if msg else "")
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
<div class="field"><label>Username</label>
<input type="text" name="username" class="input" required autofocus></div>
<div class="field"><label>Password</label>
<input type="password" name="password" class="input" required></div>
<div class="actions">
<button type="submit" class="btn btn-primary">Login</button></div>
</form></div>
<div class="footer">
<a href="https://github.com/arnstarn/mcp-server-qnap-qvs"
target="_blank">mcp-server-qnap-qvs</a> v{VERSION}</div>
</div></body></html>"""


def render_wizard(step: int = 1, values: dict | None = None,
                  msg: str = "", mt: str = "info", user: str = "") -> str:
    values = values or {}
    msg_html = (f'<div class="msg msg-{mt}">{html.escape(msg)}</div>'
                if msg else "")

    steps_bar = f"""
<div style="display:flex;gap:8px;margin-bottom:16px">
<div class="step-n" style="background:{'#238636' if step>=1 else '#30363d'}">1</div>
<div style="flex:1;height:2px;background:{'#238636' if step>=2 else '#30363d'};
align-self:center"></div>
<div class="step-n" style="background:{'#238636' if step>=2 else '#30363d'}">2</div>
</div>"""

    if step == 1:
        hv = html.escape(values.get("QNAP_HOST", "localhost"))
        pv = html.escape(values.get("QNAP_PORT", "443"))
        uv = html.escape(values.get("QNAP_USERNAME", ""))
        pwv = html.escape(values.get("QNAP_PASSWORD", ""))
        sv = values.get("QNAP_VERIFY_SSL", "false")
        sf = "selected" if sv != "true" else ""
        st = "selected" if sv == "true" else ""
        content = f"""{msg_html}
<div class="card"><h2>Step 1: QNAP Connection</h2>
<p class="hint" style="margin-bottom:12px">Enter the credentials you use
to log into the QNAP web UI.</p>
<form method="POST" action="/wizard/1">
<div class="field"><label>QNAP Host</label>
<input type="text" name="QNAP_HOST" value="{hv}" class="input"
id="field_QNAP_HOST" placeholder="localhost"></div>
<div class="field"><label>HTTPS Port</label>
<input type="text" name="QNAP_PORT" value="{pv}" class="input"></div>
<div class="field"><label>Username</label>
<input type="text" name="QNAP_USERNAME" value="{uv}" class="input"></div>
<div class="field"><label>Password</label>
<input type="password" name="QNAP_PASSWORD" value="{pwv}" class="input"></div>
<div class="field"><label>Verify SSL</label>
<select name="QNAP_VERIFY_SSL" class="input">
<option value="false" {sf}>false (self-signed, typical)</option>
<option value="true" {st}>true</option></select></div>
<div class="actions">
<button type="submit" class="btn btn-primary">Test &amp; Continue</button>
</div></form></div>
<script>// QNAP_HOST defaults to localhost (server runs on the NAS)</script>"""
    elif step == 2:
        tv = html.escape(values.get("MCP_AUTH_TOKEN", ""))
        hidden = "".join(
            f'<input type="hidden" name="{k}" value="{html.escape(v)}">'
            for k, v in values.items() if k != "MCP_AUTH_TOKEN"
        )
        content = f"""{msg_html}
<div class="card"><h2>Step 2: MCP Auth Token</h2>
<p class="hint" style="margin-bottom:12px">
This token is a shared secret between the server and your AI client.
Click Generate to create one.</p>
<form method="POST" action="/wizard/2">{hidden}
<div class="field"><label>Auth Token</label>
<div class="input-row">
<input type="text" name="MCP_AUTH_TOKEN" value="{tv}"
class="input" id="field_MCP_AUTH_TOKEN">
<button type="button" class="btn btn-sm"
onclick="generateToken()">Generate</button>
<button type="button" class="btn btn-sm"
onclick="copyToken()">Copy</button></div></div>
<div class="actions">
<button type="submit" class="btn btn-primary">Save &amp; Finish</button>
</div></form></div>
<script>
function generateToken(){{
var c='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_',t='';
var a=new Uint8Array(48);crypto.getRandomValues(a);
a.forEach(function(b){{t+=c[b%c.length]}});
document.getElementById('field_MCP_AUTH_TOKEN').value=t}}
function copyToken(){{var f=document.getElementById('field_MCP_AUTH_TOKEN');
navigator.clipboard.writeText(f.value).then(function(){{f.select()}})}}
</script>"""
    else:
        content = ""

    body = f"""
<h1>Setup Wizard</h1>
<p class="subtitle">First-time configuration</p>
{steps_bar}{content}"""
    return _page("Setup", "", body, user)
