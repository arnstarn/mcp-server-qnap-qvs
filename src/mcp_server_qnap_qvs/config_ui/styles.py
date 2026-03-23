"""CSS and JavaScript constants for the config UI."""

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
