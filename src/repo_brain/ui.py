from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .core import Brain

HTML = """<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>Repo Brain</title><style>
:root{color-scheme:dark;font-family:Inter,system-ui,sans-serif;background:#0b1020;color:#e7ecff}body{max-width:1100px;margin:0 auto;padding:24px}h1{margin:0 0 4px}small{color:#9ca9d6}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:24px 0}.card{background:#151d36;border:1px solid #2a365b;border-radius:12px;padding:16px}.value{font-size:28px;font-weight:700;color:#8be9fd}.search{display:flex;gap:8px;margin:18px 0}.search input{flex:1;padding:12px;border-radius:8px;border:1px solid #3b4b79;background:#0f162b;color:#fff}.search button{padding:12px 18px;border:0;border-radius:8px;background:#6c63ff;color:#fff}.result{padding:12px 0;border-bottom:1px solid #29365f}.path{font-family:ui-monospace,monospace;color:#9ef0a0}.stale{color:#ffb86c}.muted{color:#a9b4d8}</style></head><body><h1>Repo Brain</h1><small>Memory guides discovery. Current source code determines truth.</small><div id='stats' class='grid'></div><div class='search'><input id='query' placeholder='Ask where to change something…'><button onclick='search()'>Search</button></div><section id='results'></section><script>
async function load(){const s=await (await fetch('/api/status')).json();document.getElementById('stats').innerHTML=[['Files',s.files],['Coverage',s.semantic_coverage+'%'],['Fresh',s.states?.fresh||0],['Stale',s.states?.stale||0],['Needs review',s.states?.needs_review||0]].map(x=>`<div class='card'><div class='muted'>${x[0]}</div><div class='value'>${x[1]}</div></div>`).join('')}async function search(){const q=document.getElementById('query').value;const data=await (await fetch('/api/context?q='+encodeURIComponent(q))).json();document.getElementById('results').innerHTML=(data.results||[]).map(r=>`<div class='result'><div class='path'>${r.path} <span class='${r.state==='stale'?'stale':''}'>${r.state}</span> · score ${r.score}</div><div>${r.summary||''}</div><div class='muted'>${(r.symbols||[]).map(s=>s.name).join(', ')}</div></div>`).join('')}load()</script></body></html>"""


def serve(brain: Brain, host: str = "127.0.0.1", port: int = 8765) -> None:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args: object) -> None:
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/":
                    data, content_type = HTML.encode(), "text/html; charset=utf-8"
                elif parsed.path == "/api/status":
                    data, content_type = json.dumps(brain.status(), default=str).encode(), "application/json"
                elif parsed.path == "/api/context":
                    query = parse_qs(parsed.query).get("q", [""])[0]
                    data, content_type = json.dumps(brain.context(query), default=str).encode(), "application/json"
                elif parsed.path == "/api/files":
                    data, content_type = json.dumps([dict(r) for r in brain.db.fetchall("SELECT relative_path,analysis_state,language,category FROM files WHERE repository_id=? AND status='active' ORDER BY relative_path", (brain.repository_id,))]).encode(), "application/json"
                else:
                    self.send_error(404); return
                self.send_response(200); self.send_header("Content-Type", content_type); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
            except (OSError, ValueError, KeyError) as exc:
                self.send_error(500, str(exc))

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Repo Brain UI: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
