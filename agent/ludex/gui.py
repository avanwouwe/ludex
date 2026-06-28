"""Browser-based GUI: installer, activity detect, and uninstall (stdlib only).

Shown when the binary is launched with no arguments (double-clicked). Starts a
tiny web server bound to 127.0.0.1 and opens the browser to a single-page app
that handles the full lifecycle:

  * Install    — validate credentials and register the system service
  * Detect App — scan running processes and push an activity definition
  * Uninstall  — remove the service and (on macOS) the app bundle

The token is never sent to the browser; all backend calls happen server-side.
"""

from __future__ import annotations

import json
import re
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .installer import validate_and_install
from .transport import BackendError


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    return slug or "activity"


# ---------------------------------------------------------------------------
# Single-page HTML app
# ---------------------------------------------------------------------------
_PAGE_HTML = """\
<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ludex</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;
     max-width:560px;margin:40px auto;padding:0 20px;color:#1f2937;line-height:1.55}
h1{font-size:22px;font-weight:800;color:#1a3c5e}
.sub{color:#6b7280;font-size:13px;margin:2px 0 28px}
h2{font-size:14px;font-weight:700;margin:0 0 6px;color:#1a3c5e}
p{color:#374151;font-size:14px;margin:0 0 10px}
label{display:block;font-weight:600;font-size:13px;margin:14px 0 4px}
.hint{font-weight:normal;color:#6b7280;font-size:12px}
input{width:100%;padding:8px 10px;font-size:14px;border:1px solid #d1d5db;
      border-radius:6px;outline:none;transition:border-color .15s}
input:focus{border-color:#1a3c5e;box-shadow:0 0 0 2px rgba(26,60,94,.1)}
.row{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap}
.btn{padding:8px 16px;border:none;border-radius:6px;font-size:14px;font-weight:600;
     cursor:pointer;transition:opacity .15s}
.btn:disabled{opacity:.4;cursor:default}
.prim{background:#1a3c5e;color:#fff}
.prim:not(:disabled):hover{background:#122b45}
.dang{background:#dc2626;color:#fff}
.dang:not(:disabled):hover{background:#b91c1c}
.ghost{background:#f3f4f6;color:#374151;border:1px solid #e5e7eb}
.ghost:hover{background:#e5e7eb}
.msg{margin:12px 0;padding:10px 14px;border-radius:6px;font-size:13px;white-space:pre-wrap}
.ok{background:#f0fdf4;border:1px solid #bbf7d0;color:#15803d}
.err{background:#fef2f2;border:1px solid #fecaca;color:#dc2626}
hr{border:none;border-top:1px solid #e5e7eb;margin:24px 0}
table{width:100%;border-collapse:collapse;font-size:13px;margin:10px 0}
thead th{text-align:left;padding:5px 8px;border-bottom:2px solid #e5e7eb;
         font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:#9ca3af}
tbody tr{cursor:pointer}
tbody tr:hover{background:#f8fafc}
tbody tr.sel{background:#eff6ff}
td{padding:6px 8px;border-bottom:1px solid #f3f4f6}
</style>
</head><body>
<h1>Ludex</h1>
<p class="sub">Activity monitoring agent</p>
<div id="app"><p style="color:#9ca3af">Loading…</p></div>
<script>
var S={
  view:'loading',url:'',
  procs:[],sel:null,scanning:false,
  topMsg:'',topOk:false,
  dMsg:'',dOk:false,
  iMsg:'',iOk:false,
  uMsg:'',uOk:false,updating:false
};

function el(id){return document.getElementById(id);}

function esc(s){
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;')
                      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function mkMsg(txt,ok){
  return txt?('<div class="msg '+(ok?'ok':'err')+'">'+esc(txt)+'</div>'):'';
}

function render(){
  var a=el('app');
  if(S.view==='install'){renderInstall(a);}
  else if(S.view==='manage'){renderManage(a);}
}

function renderInstall(a){
  a.innerHTML=
    '<p>Enter the details from your Ludex dashboard to install the agent on this computer.</p>'+
    '<label>Dashboard URL'+
    '  <span class="hint">(the /exec URL from Apps Script — not the Google Sheet link)</span>'+
    '</label>'+
    '<input id="iUrl" type="url" placeholder="https://script.google.com/…/exec" autocomplete="off">'+
    '<label>Shared key</label>'+
    '<input id="iTok" type="password" autocomplete="new-password">'+
    '<div class="row">'+
    '  <button class="btn prim" id="iBtn" onclick="doInstall()">Install</button>'+
    '</div>'+
    mkMsg(S.iMsg,S.iOk);
  el('iUrl').focus();
}

function renderManage(a){
  var h=mkMsg(S.topMsg,S.topOk);
  h+='<p style="font-size:13px;color:#6b7280">Connected to backend</p>';

  // ── Detect App ─────────────────────────────────────────────────────────────
  h+='<h2>Add tracked activity</h2>'+
     '<p>Scan running processes and register one as a monitored activity on this computer.</p>'+
     '<button class="btn prim" id="sBtn" onclick="doScan()"'+(S.scanning?' disabled':'')+'>'+
     (S.scanning?'Scanning…':'Scan running processes')+
     '</button>';

  if(S.procs.length){
    h+='<table><thead><tr><th></th><th>Process</th><th>CPU%</th><th>Command</th></tr></thead><tbody>';
    S.procs.forEach(function(p,i){
      var s=S.sel===i;
      var cmd=esc((p.exe||p.cmdline||'').split('/').pop()||p.name);
      h+='<tr class="'+(s?'sel':'')+'" onclick="pick('+i+')"'+
         ' title="'+esc(p.cmdline||p.exe||'')+'">'+
         '<td style="width:20px;color:#1a3c5e;font-weight:700">'+(s?'✓':'')+'</td>'+
         '<td><b>'+esc(p.name)+'</b></td>'+
         '<td>'+p.cpu.toFixed(1)+'</td>'+
         '<td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+cmd+'</td>'+
         '</tr>';
    });
    h+='</tbody></table>';
  }

  if(S.sel!==null){
    h+='<label>Activity name</label>'+
       '<input id="aName" type="text" placeholder="e.g. League of Legends" autocomplete="off">'+
       '<label>Admin password</label>'+
       '<input id="aPwd" type="password" autocomplete="new-password">'+
       '<div class="row">'+
       '  <button class="btn prim" id="dBtn" onclick="doDetect()">Add activity</button>'+
       '</div>';
  }

  h+=mkMsg(S.dMsg,S.dOk);

  // ── Update ──────────────────────────────────────────────────────────────────
  h+='<hr><h2>Update agent</h2>'+
     '<p>Reinstall the agent binary and restart the service, keeping existing credentials.</p>'+
     '<button class="btn prim" id="uBtn" onclick="doUpdate()"'+(S.updating?' disabled':'')+'>'+
     (S.updating?'Updating…':'Update agent')+
     '</button>'+
     mkMsg(S.uMsg,S.uOk);

  // ── Uninstall ───────────────────────────────────────────────────────────────
  h+='<hr><h2>Uninstall</h2>'+
     '<p>Remove Ludex from this computer. Your dashboard data is not affected.</p>'+
     '<button class="btn dang" onclick="doUninstall()">Uninstall Ludex</button>';

  // ── Close ───────────────────────────────────────────────────────────────────
  h+='<hr><button class="btn ghost" onclick="doQuit()">Close</button>';

  a.innerHTML=h;
}

// ── Actions ──────────────────────────────────────────────────────────────────

function pick(i){
  S.sel=(S.sel===i?null:i);
  S.dMsg='';S.dOk=false;
  render();
}

function post(url,data,cb){
  fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(data||{})})
  .then(function(r){return r.json();}).then(cb)
  .catch(function(e){cb({ok:false,error:String(e)});});
}

function doInstall(){
  var url=(el('iUrl').value||'').trim(),tok=(el('iTok').value||'');
  if(!url){S.iMsg='Dashboard URL is required.';S.iOk=false;render();return;}
  if(url.indexOf('docs.google.com/spreadsheets')!==-1){
    S.iMsg='That looks like a Google Sheet link, not the Dashboard URL.\\nYou need the Web app URL (ending in /exec).';
    S.iOk=false;render();return;
  }
  el('iBtn').disabled=true;
  S.iMsg='Validating and installing…';S.iOk=false;render();
  post('/install',{url:url,token:tok},function(d){
    if(d.ok){
      S.view='manage';S.url=url;
      S.topMsg='Installed ✓ — Ludex is now running and will start on login.';S.topOk=true;
    } else {
      if(el('iBtn'))el('iBtn').disabled=false;
      S.iMsg=d.error||'Installation failed.';S.iOk=false;
    }
    render();
  });
}

function doScan(){
  S.scanning=true;S.procs=[];S.sel=null;S.dMsg='';S.topMsg='';render();
  fetch('/processes').then(function(r){return r.json();}).then(function(d){
    S.scanning=false;
    if(d.ok){S.procs=d.processes;}
    else{S.dMsg=d.error||'Scan failed.';S.dOk=false;}
    render();
  }).catch(function(e){S.scanning=false;S.dMsg=String(e);S.dOk=false;render();});
}

function doDetect(){
  var nm=(el('aName')?el('aName').value.trim():'');
  var pw=(el('aPwd')?el('aPwd').value.trim():'');
  if(!nm){S.dMsg='Activity name is required.';S.dOk=false;render();return;}
  if(!pw){S.dMsg='Admin password is required.';S.dOk=false;render();return;}
  if(el('dBtn'))el('dBtn').disabled=true;
  post('/detect',{name:nm,admin_password:pw,process:S.procs[S.sel]},function(d){
    S.dMsg=d.ok?d.message:(d.error||'Failed.');
    S.dOk=!!d.ok;
    if(d.ok){S.sel=null;S.procs=[];}
    render();
  });
}

function doUpdate(){
  S.updating=true;S.uMsg='';render();
  post('/update',{},function(d){
    S.updating=false;
    S.uMsg=d.ok?d.message:(d.error||'Update failed.');
    S.uOk=!!d.ok;
    render();
  });
}

function doUninstall(){
  if(!confirm('Remove Ludex from this computer?'))return;
  post('/uninstall',{},function(d){
    if(d.ok){
      el('app').innerHTML='<div class="msg ok">Ludex removed. You can close this tab.</div>';
    } else {
      alert('Uninstall failed: '+(d.error||'unknown error'));
    }
  });
}

function doQuit(){
  post('/quit',{},function(){
    el('app').innerHTML='<p style="color:#9ca3af">You can close this tab.</p>';
  });
}

// ── Init: check if already installed ─────────────────────────────────────────
fetch('/status')
  .then(function(r){return r.json();})
  .then(function(d){
    S.url=d.backend_url||'';
    S.view=d.installed?'manage':'install';
    render();
  })
  .catch(function(){S.view='install';render();});
</script>
</body></html>
"""

_PAGE = _PAGE_HTML.encode()


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class _Handler(BaseHTTPRequestHandler):
    server_ref = None

    def log_message(self, *a):
        pass

    def _json(self, code: int, obj: dict):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(_PAGE)))
            self.end_headers()
            self.wfile.write(_PAGE)
        elif self.path == "/status":
            self._handle_status()
        elif self.path == "/processes":
            self._handle_processes()
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        try:
            data = self._read_json()
        except Exception:
            data = {}
        if self.path == "/install":
            self._handle_install(data)
        elif self.path == "/detect":
            self._handle_detect(data)
        elif self.path == "/update":
            self._handle_update()
        elif self.path == "/uninstall":
            self._handle_uninstall()
        elif self.path == "/quit":
            self._json(200, {"ok": True})
            threading.Thread(target=self._shutdown_soon, daemon=True).start()
        else:
            self._json(404, {"error": "not found"})

    # ── Route handlers ──────────────────────────────────────────────────────

    def _handle_status(self):
        from .platform import get_platform
        cfg = get_platform().installed_config()
        if cfg:
            self._json(200, {"installed": True, "backend_url": cfg["backend_url"]})
        else:
            self._json(200, {"installed": False, "backend_url": ""})

    def _handle_install(self, data: dict):
        try:
            msg = validate_and_install(data.get("url", ""), data.get("token", ""))
            self._json(200, {"ok": True, "message": msg})
        except (ValueError, BackendError) as e:
            self._json(200, {"ok": False, "error": str(e)})
        except Exception as e:
            self._json(200, {"ok": False, "error": str(e)})

    def _handle_processes(self):
        from .detection import list_active_candidates
        try:
            rows = list_active_candidates()
            self._json(200, {"ok": True, "processes": rows[:30]})
        except Exception as e:
            self._json(200, {"ok": False, "error": str(e)})

    def _handle_detect(self, data: dict):
        import yaml
        from .detection import build_definition, build_match_block
        from .platform import get_platform
        from .transport import BackendClient

        platform = get_platform()
        cfg = platform.installed_config()
        if not cfg:
            self._json(200, {"ok": False, "error": "Ludex is not installed."})
            return

        name = (data.get("name") or "").strip()
        admin_password = (data.get("admin_password") or "").strip()
        process = data.get("process")

        if not name:
            self._json(200, {"ok": False, "error": "Activity name is required."})
            return
        if not admin_password:
            self._json(200, {"ok": False, "error": "Admin password is required."})
            return
        if not isinstance(process, dict):
            self._json(200, {"ok": False, "error": "No process selected."})
            return

        activity_id = _slugify(name)
        client = BackendClient(cfg["backend_url"], cfg["token"])

        # Fetch existing definition for per-platform merging (same logic as CLI detect-app).
        existing = None
        res = client.call_one("GetConfig", {})
        if res.ok:
            for t in res.data.get("activity_types", []):
                if t.get("activity_id") == activity_id:
                    try:
                        existing = yaml.safe_load(t.get("definition") or "")
                    except Exception:
                        pass
                    break

        os_key = platform.os_key
        block = build_match_block(process)
        if isinstance(existing, dict):
            definition = dict(existing)
            platforms = dict(definition.get("platforms") or {})
            platforms[os_key] = {"match_any": [block]}
            definition["platforms"] = platforms
            definition.pop("match_any", None)
            definition.setdefault("min_cpu_percent", 5.0)
            definition.setdefault("limits", {"daily_max_minutes": 120, "warn_before_minutes": 10})
        else:
            definition = build_definition(activity_id, process, os_key)

        res = client.call_one("PutActivityType", {
            "admin_password": admin_password,
            "activity_id": activity_id,
            "name": name,
            "definition": json.dumps(definition),
            "enabled": True,
        })
        if res.ok:
            verb = "created" if res.data.get("created") else "updated"
            self._json(200, {"ok": True, "message": f"Activity '{name}' {verb}."})
        else:
            self._json(200, {"ok": False, "error": f"Backend rejected: {res.error}"})

    def _handle_update(self):
        from .platform import get_platform
        cfg = get_platform().installed_config()
        if not cfg:
            self._json(200, {"ok": False, "error": "Not installed — use Install instead."})
            return
        try:
            msg = validate_and_install(cfg["backend_url"], cfg["token"])
            self._json(200, {"ok": True, "message": msg})
        except (ValueError, BackendError) as e:
            self._json(200, {"ok": False, "error": str(e)})
        except Exception as e:
            self._json(200, {"ok": False, "error": str(e)})

    def _handle_uninstall(self):
        from .platform import get_platform
        try:
            msg = get_platform().uninstall_service()
            self._json(200, {"ok": True, "message": msg})
            threading.Thread(target=self._shutdown_soon, daemon=True).start()
        except Exception as e:
            self._json(200, {"ok": False, "error": str(e)})

    def _shutdown_soon(self):
        time.sleep(0.5)
        if _Handler.server_ref:
            _Handler.server_ref.shutdown()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _build_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.daemon_threads = True  # don't let lingering handler threads block shutdown
    _Handler.server_ref = server
    return server


def run_installer():
    server = _build_server()
    url = "http://127.0.0.1:%d/" % server.server_address[1]
    print("Ludex running. If your browser didn't open, go to: " + url)
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
