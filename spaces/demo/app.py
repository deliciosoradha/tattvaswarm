#!/usr/bin/env python3
"""TattvaSwarm live demo — minimal stdlib web app (Hugging Face Spaces, Docker SDK).

One page, one endpoint:
  GET  /            tiny chat UI
  POST /api/route   run one prompt through the tiered router
  GET  /healthz     liveness + configuration check

The shared demo key is protected by a small in-memory rate limit. Honest
errors from the router are shown as-is.
"""

from __future__ import annotations

import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tattva_swarm import __version__  # noqa: E402
from tattva_swarm.router import route  # noqa: E402

PORT = int(os.environ.get("PORT", "7860"))
MAX_PROMPT_CHARS = 1500
MAX_REPLY_TOKENS = 400
RATE_LIMIT_PER_HOUR = 15
_RATE: dict[str, tuple[float, int]] = {}


def _allowed(ip: str, limit: int = RATE_LIMIT_PER_HOUR, window: int = 3600) -> bool:
    now = time.time()
    start, count = _RATE.get(ip, (now, 0))
    if now - start > window:
        start, count = now, 0
    if count >= limit:
        return False
    _RATE[ip] = (start, count + 1)
    return True


PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>TattvaSwarm demo</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
 body{font-family:ui-monospace,Menlo,monospace;background:#0d0f14;color:#e6e6e6;margin:0;padding:2rem;max-width:52rem}
 h1{font-weight:600;font-size:1.25rem;margin:0 0 .25rem} .sub{color:#8a93a5;margin-bottom:1.5rem}
 textarea,input,select,button{font:inherit;background:#161a22;color:#e6e6e6;border:1px solid #2a3040;border-radius:.5rem;padding:.6rem}
 textarea{width:100%;height:5rem} button{cursor:pointer;background:#2a3040} button:hover{background:#343c50}
 pre{background:#12151d;border:1px solid #2a3040;border-radius:.5rem;padding:.75rem;white-space:pre-wrap;word-break:break-word}
 .row{display:flex;gap:.5rem;margin:.6rem 0} .muted{color:#8a93a5;font-size:.85rem}
</style></head><body>
<h1>TattvaSwarm — sovereign personal AI swarm</h1>
<div class="sub">tiered routing · NVIDIA Nemotron on Nebius Token Factory · local-first memory</div>
<textarea id="p" placeholder="Ask something… e.g. 'Say hello in one short line.'"></textarea>
<div class="row">
 <select id="tier">
  <option value="auto">auto (classifier)</option><option value="small">small (local)</option>
  <option value="normal">normal (Nano)</option><option value="reasoning">reasoning (Super)</option>
  <option value="heavy">heavy (Ultra)</option>
 </select>
 <button onclick="go()">Route it</button>
 <span class="muted" id="hint">demo key · rate-limited · replies trimmed</span>
</div>
<pre id="out">—</pre>
<script>
async function go(){
 const out=document.getElementById('out'); out.textContent='…';
 try{
  const r=await fetch('/api/route',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({prompt:document.getElementById('p').value,tier:document.getElementById('tier').value})});
  const j=await r.json(); out.textContent=JSON.stringify(j,null,2);
 }catch(e){ out.textContent='request failed: '+e; }
}
</script></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = f"tattva-swarm-demo/{__version__}"

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict) -> None:
        self._send(code, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/index.html"):
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        elif self.path == "/healthz":
            self._json(200, {
                "ok": True,
                "version": __version__,
                "key_configured": bool(os.environ.get("NEBIUS_API_KEY", "").strip()),
                "models": {
                    "normal": os.environ.get("TATTVA_MODEL_FAST", ""),
                    "reasoning": os.environ.get("TATTVA_MODEL_REASONING", ""),
                    "heavy": os.environ.get("TATTVA_MODEL_HEAVY", ""),
                },
            })
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/route":
            self._json(404, {"error": "not found"})
            return
        ip = self.client_address[0]
        if not _allowed(ip):
            self._json(429, {"error": "rate limit reached — try again later (15 calls/hour per client)"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(min(length, 64_000)).decode("utf-8"))
        except Exception:
            self._json(400, {"error": "invalid JSON body"})
            return
        prompt = str(payload.get("prompt", ""))[:MAX_PROMPT_CHARS].strip()
        tier = str(payload.get("tier", "auto"))
        if not prompt:
            self._json(400, {"error": "empty prompt"})
            return
        valid = {"auto", "small", "normal", "reasoning", "heavy", "research"}
        if tier not in valid:
            self._json(400, {"error": f"tier must be one of {sorted(valid)}"})
            return
        try:
            max_tokens = 120 if tier == "small" else MAX_REPLY_TOKENS
            result = route(prompt, tier=tier, max_tokens=max_tokens)
            self._json(200, result)
        except Exception as exc:  # noqa: BLE001 — surface exactly, never fake
            self._json(500, {"error": f"{type(exc).__name__}: {exc}"})

    def log_message(self, fmt: str, *args) -> None:  # keep stdout clean-ish
        sys.stderr.write(f"{self.address_string()} - {fmt % args}\n")


def main() -> None:
    print(f"TattvaSwarm demo on :{PORT} — key_configured={bool(os.environ.get('NEBIUS_API_KEY', '').strip())}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
