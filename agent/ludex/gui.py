"""Graphical installer via a local browser form (stdlib only — no GUI toolkit dependency).

Shown when the binary is launched with no arguments (e.g. double-clicked). Starts a tiny web
server bound to 127.0.0.1, opens the browser to a form, and installs on submit. Using the browser
avoids bundling tkinter/Qt (fragile in frozen builds) and gives a styled, familiar UI.
"""

from __future__ import annotations

import json
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .installer import validate_and_install
from .transport import BackendError

_PAGE = b"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Install Ludex</title><style>
 body{font-family:-apple-system,Segoe UI,Arial,sans-serif;max-width:520px;margin:40px auto;padding:0 16px;color:#222}
 h1{font-size:20px} label{display:block;font-weight:bold;margin:16px 0 4px}
 .desc{color:#666;font-weight:normal;font-size:13px}
 input{width:100%;box-sizing:border-box;padding:9px;font-size:14px}
 button{margin-top:20px;padding:10px 18px;font-size:14px}
 #msg{margin-top:16px;white-space:pre-wrap}
 .ok{color:#080} .err{color:#a00}
</style></head><body>
 <h1>Install Ludex on this computer</h1>
 <p class="desc">Enter the details from your Ludex dashboard.</p>
 <label>Dashboard URL <span class="desc">(the web app URL ending in /exec — not the Google Sheet link)</span></label>
 <input id="url" type="text" autocomplete="off" autofocus>
 <label>Shared key</label>
 <input id="token" type="password" autocomplete="off">
 <button id="go" onclick="install()">Install</button>
 <div id="msg"></div>
<script>
 function msg(t,c){var m=document.getElementById('msg');m.textContent=t;m.className=c||'';}
 function install(){
   var url=document.getElementById('url').value.trim(), token=document.getElementById('token').value;
   if(url.indexOf('docs.google.com/spreadsheets')!==-1){
     msg('That looks like a Google Sheet link, not the Dashboard URL.\\n\\nYou need the Web app URL (ending in /exec).\\nIn Apps Script: Deploy \\u2192 Manage deployments \\u2192 copy the /exec URL.','err');
     return;
   }
   document.getElementById('go').disabled=true; msg('Validating and installing...');
   fetch('/install',{method:'POST',headers:{'Content-Type':'application/json'},
     body:JSON.stringify({url:url,token:token})})
   .then(function(r){return r.json();})
   .then(function(d){
     if(d.ok){ msg('Installed \\u2713 \\u2014 Ludex is running. You can close this tab.','ok'); }
     else { document.getElementById('go').disabled=false; msg('Failed: '+d.error,'err'); }
   })
   .catch(function(e){ document.getElementById('go').disabled=false; msg('Error: '+e,'err'); });
 }
</script></body></html>"""


class _Handler(BaseHTTPRequestHandler):
    server_ref = None  # set by _build_server

    def log_message(self, *a):
        pass  # quiet

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, "text/html; charset=utf-8", _PAGE)
        else:
            self._send(404, "text/plain", b"not found")

    def do_POST(self):
        if self.path != "/install":
            self._send(404, "text/plain", b"not found")
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
            msg = validate_and_install(data.get("url", ""), data.get("token", ""))
            self._send(200, "application/json", json.dumps({"ok": True, "message": msg}).encode())
            threading.Thread(target=self._shutdown_soon, daemon=True).start()
        except (ValueError, BackendError) as e:
            self._send(200, "application/json", json.dumps({"ok": False, "error": str(e)}).encode())
        except Exception as e:
            self._send(200, "application/json", json.dumps({"ok": False, "error": str(e)}).encode())

    def _shutdown_soon(self):
        time.sleep(1.0)
        if _Handler.server_ref:
            _Handler.server_ref.shutdown()


def _build_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    _Handler.server_ref = server
    return server


def run_installer():
    server = _build_server()
    url = "http://127.0.0.1:%d/" % server.server_address[1]
    print("Ludex installer running. If your browser didn't open, go to: " + url)
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
