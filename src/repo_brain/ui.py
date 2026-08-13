from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .core import Brain

HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Repo Brain — directory memory</title>
<style>
:root{color-scheme:dark;font-family:Inter,system-ui,sans-serif;background:#090d19;color:#ecf2ff}*{box-sizing:border-box}body{margin:0;min-height:100vh}header{padding:24px 32px;border-bottom:1px solid #263250;background:#10182c}h1{margin:0 0 5px;font-size:28px}small,.muted{color:#9eadd1}.layout{display:grid;grid-template-columns:280px 1fr;min-height:calc(100vh - 96px)}aside{padding:20px;border-right:1px solid #263250;background:#0d1426}.main{padding:24px;max-width:1200px;width:100%}.directory-list{display:flex;flex-direction:column;gap:6px;margin-top:18px}.directory-list button{border:1px solid transparent;border-radius:8px;padding:9px 10px;text-align:left;background:transparent;color:#d9e4ff;cursor:pointer}.directory-list button:hover,.directory-list button.active{background:#1b2a4b;border-color:#3f5f9d}.directory-list button .count{float:right;color:#86e1ff}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:18px 0}.card{background:#121c33;border:1px solid #2b3b63;border-radius:12px;padding:14px}.value{font-size:25px;font-weight:700;color:#86e1ff}.search{display:flex;gap:8px;margin:20px 0}.search input{flex:1;padding:12px;border-radius:8px;border:1px solid #3f527f;background:#0c1426;color:#fff}.search select,.search button{padding:12px;border-radius:8px;border:1px solid #3f527f;background:#162544;color:#fff}.search button{background:#6155db;border-color:#6155db;cursor:pointer}.group{margin:18px 0;border:1px solid #2b3b63;border-radius:12px;overflow:hidden}.group h3{margin:0;padding:12px 15px;background:#172442;color:#a8ecff}.result{padding:13px 15px;border-top:1px solid #243353}.path{font-family:ui-monospace,monospace;color:#a5f1aa}.badge{margin-left:8px;color:#ffbf75}.symbol{color:#a7b5d9;font-size:13px;margin-top:5px}.empty{padding:24px;border:1px dashed #3a4b73;border-radius:10px;color:#9eadd1}@media(max-width:760px){.layout{grid-template-columns:1fr}aside{border-right:0;border-bottom:1px solid #263250}}
</style></head><body>
<header><h1>Repo Brain</h1><small>Directory-scoped memory. Memory guides discovery; current source code determines truth.</small></header>
<div class="layout"><aside><strong>Directories</strong><div id="directories" class="directory-list"></div></aside><main class="main"><div id="stats" class="grid"></div><div id="efficiency" class="muted"></div><div class="search"><input id="query" placeholder="Describe the change you need to make…"><select id="scope"><option value="">All directories (grouped)</option></select><button onclick="search()">Find context</button></div><div id="hint" class="muted">Select a directory to isolate retrieval, or search all directories while keeping results grouped.</div><section id="results"></section></main></div>
<script>
let selected='';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function load(){const status=await (await fetch('/api/status')).json();document.getElementById('stats').innerHTML=[['Files',status.files],['Directories',status.directories||0],['Coverage',status.semantic_coverage+'%'],['Fresh',status.states?.fresh||0],['Stale',status.states?.stale||0]].map(x=>`<div class="card"><div class="muted">${x[0]}</div><div class="value">${x[1]}</div></div>`).join('');const dirs=await (await fetch('/api/directories')).json();const list=document.getElementById('directories'),scope=document.getElementById('scope');list.innerHTML='';scope.innerHTML='<option value="">All directories (grouped)</option>';dirs.forEach(d=>{const option=document.createElement('option');option.value=d.path;option.textContent=d.path+` (${d.active_file_count})`;scope.appendChild(option);const button=document.createElement('button');button.innerHTML=`<span>${esc(d.path)}</span><span class="count">${d.active_file_count}</span>`;button.onclick=()=>selectDirectory(d.path,button);button.dataset.path=d.path;list.appendChild(button)})}
function selectDirectory(path,button){selected=path;document.getElementById('scope').value=path;document.querySelectorAll('.directory-list button').forEach(b=>b.classList.remove('active'));button?.classList.add('active');search()}
async function search(){const q=document.getElementById('query').value||'architecture';const scope=document.getElementById('scope').value;selected=scope;const data=await (await fetch('/api/context?q='+encodeURIComponent(q)+'&directory='+encodeURIComponent(scope))).json();const results=document.getElementById('results');const groups=data.groups||{};const names=Object.keys(groups);document.getElementById('hint').textContent=`Scope: ${scope||'all directories'} · estimated context: ${data.estimated_tokens||0} tokens · read order is intentional.`;results.innerHTML=names.length?names.map(dir=>`<div class="group"><h3>${esc(dir)} <span class="muted">(${groups[dir].length} files)</span></h3>${groups[dir].map(r=>`<div class="result"><div class="path">${esc(r.path)} <span class="badge">${esc(r.state)} · ${r.score}</span></div><div>${esc(r.summary||'No semantic summary yet')}</div><div class="symbol">${(r.symbols||[]).map(s=>esc(s.name)).join(', ')}</div></div>`).join('')}</div>`).join(''):'<div class="empty">No relevant files in this directory scope. Try a broader directory or run <code>repo-brain scan</code>.</div>'}
async function loadEfficiency(){const data=await (await fetch('/api/efficiency')).json();if(data.runs){document.getElementById('efficiency').textContent=`Recorded retrievals: ${data.runs} · estimated tokens: ${data.totals.estimated_tokens} · compacted tokens: ${data.totals.compacted_tokens} (${data.compaction_percent}%) · average time: ${data.averages.elapsed_ms} ms`}}
load();loadEfficiency();
</script></body></html>"""


def serve(brain: Brain, host: str = "127.0.0.1", port: int = 8765) -> None:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args: object) -> None:
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            try:
                query = parse_qs(parsed.query)
                if parsed.path == "/":
                    data, content_type = HTML.encode("utf-8"), "text/html; charset=utf-8"
                elif parsed.path == "/api/status":
                    data, content_type = json.dumps(brain.status(), ensure_ascii=False, default=str).encode("utf-8"), "application/json; charset=utf-8"
                elif parsed.path == "/api/directories":
                    data, content_type = json.dumps(brain.directories(), ensure_ascii=False, default=str).encode("utf-8"), "application/json; charset=utf-8"
                elif parsed.path == "/api/efficiency":
                    directory = query.get("directory", [None])[0] or None
                    data, content_type = json.dumps(brain.efficiency(int(query.get("limit", [30])[0]), directory), ensure_ascii=False, default=str).encode("utf-8"), "application/json; charset=utf-8"
                elif parsed.path == "/api/directory":
                    path = query.get("path", ["."])[0]
                    data, content_type = json.dumps(brain.directory_details(path), ensure_ascii=False, default=str).encode("utf-8"), "application/json; charset=utf-8"
                elif parsed.path == "/api/context":
                    task = query.get("q", [""])[0]
                    directory = query.get("directory", [None])[0] or None
                    data, content_type = json.dumps(brain.context(task, directory=directory), ensure_ascii=False, default=str).encode("utf-8"), "application/json; charset=utf-8"
                elif parsed.path == "/api/files":
                    directory = query.get("directory", [None])[0] or None
                    rows = brain.search("", limit=500, directory=directory)
                    data, content_type = json.dumps(rows, ensure_ascii=False, default=str).encode("utf-8"), "application/json; charset=utf-8"
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
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
