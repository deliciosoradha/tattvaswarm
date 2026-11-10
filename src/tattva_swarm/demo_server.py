"""Demo web server — stdlib-only HTTP surface for the TattvaSwarm demo.

Endpoints::

    GET  /            self-contained HTML playground (no external assets)
    GET  /healthz     liveness + honest backend snapshot
    POST /api/route   {"prompt": "...", "tier": "auto"} -> router result (JSON)

Run::

    python -m tattva_swarm.demo_server --host 127.0.0.1 --port 8000

Public-deployment guardrails (this server is meant to be reachable on the
internet when used as the hackathon demo, e.g. a Nebius Serverless CPU
endpoint):

* optional bearer gate — set ``TATTVA_DEMO_TOKEN`` and POSTs require
  ``Authorization: Bearer <token>`` (off by default so the page is clickable)
* per-IP rate limit on POST — ``TATTVA_DEMO_RATE_PER_MIN`` (default 8)
* hard caps: prompt length, ``max_tokens``, body size

Honesty rule: unresolved prompts return the router's structured error; this
server never fabricates answers.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__
from .nebius import load_env_file
from .router import route, tier_models

MAX_BODY = 65_536
MAX_PROMPT = 4_000
DEFAULT_MAX_TOKENS = 512
MAX_TOKENS_CAP = 2_048

_RATE: dict[str, list[float]] = {}
_RATE_LOCK = threading.Lock()


def _rate_ok(ip: str) -> bool:
    limit = int(os.environ.get("TATTVA_DEMO_RATE_PER_MIN", "8") or "8")
    if limit <= 0:
        return True
    now = time.monotonic()
    with _RATE_LOCK:
        hits = [t for t in _RATE.get(ip, []) if now - t < 60.0]
        if len(hits) >= limit:
            _RATE[ip] = hits
            return False
        hits.append(now)
        _RATE[ip] = hits
        if len(_RATE) > 1_024:  # crude prune; demo-scale only
            for key in list(_RATE)[:512]:
                _RATE.pop(key, None)
    return True


def health() -> dict:
    load_env_file()
    key = os.environ.get("NEBIUS_API_KEY", "").strip()
    from .sandbox import backend_status

    return {
        "status": "ok",
        "service": "tattvaswarm-demo",
        "version": __version__,
        "api_key": "set" if key else "missing",
        "tiers": tier_models(),
        "sandbox": backend_status(),
    }


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TattvaSwarm — sovereign personal AI swarm</title>
<style>
:root{color-scheme:dark}
body{font-family:system-ui,sans-serif;max-width:52rem;margin:2rem auto;padding:0 1rem;background:#0b0f14;color:#e6edf3}
h1{font-size:1.4rem;margin-bottom:.2rem}
p.sub{color:#8b949e;margin-top:0;line-height:1.5}
textarea{width:100%;height:6.5rem;background:#161b22;color:#e6edf3;border:1px solid #30363d;border-radius:8px;padding:.6rem;font:inherit;box-sizing:border-box}
select,button{font:inherit;padding:.5rem .8rem;border-radius:8px;border:1px solid #30363d;background:#21262d;color:#e6edf3}
button{cursor:pointer}
#go{background:#1f6feb;border-color:#1f6feb;font-weight:600}
button:disabled{opacity:.5;cursor:wait}
pre{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:.8rem;overflow:auto;white-space:pre-wrap;min-height:6rem}
.row{display:flex;gap:.5rem;align-items:center;margin:.6rem 0;flex-wrap:wrap}
.chips button{background:#21262d;border-color:#30363d;font-size:.82rem}
#meta{color:#8b949e;font-size:.9rem}
a{color:#58a6ff}
</style></head><body>
<h1>TattvaSwarm</h1>
<p class="sub">Sovereign personal AI swarm: tiered NVIDIA Nemotron routing on Nebius Token Factory,
local-only memory, compact logical swarms, hardened code sandbox. Honest failures —
never a fabricated answer. <a href="/healthz">/healthz</a></p>
<textarea id="prompt" placeholder="Ask something — e.g. 'Analyze the trade-offs of local-first AI vs cloud-only assistants.'"></textarea>
<div class="row">
  <label>tier
    <select id="tier"><option>auto</option><option>small</option><option>normal</option><option>reasoning</option><option>heavy</option><option>research</option></select>
  </label>
  <button id="go">Route &#8594;</button><span id="meta"></span>
</div>
<div class="row chips"></div>
<pre id="out">(no request yet)</pre>
<script>
const $=s=>document.querySelector(s);
const examples=[
 "hello — handled locally, zero LLM calls",
 "Analyze the trade-offs of local-first AI vs cloud-only assistants.",
 "Synthesize a short strategy document about sovereign AI for a personal assistant.",
 "search the web for the latest Nebius Token Factory news"
];
examples.forEach(t=>{const b=document.createElement("button");b.textContent=t.length>56?t.slice(0,53)+"...":t;b.onclick=()=>{$("#prompt").value=t};$(".chips").appendChild(b)});
$("#go").onclick=async()=>{
  $("#go").disabled=true;$("#meta").textContent="routing...";$("#out").textContent="(working)";
  try{
    const r=await fetch("/api/route",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({prompt:$("#prompt").value,tier:$("#tier").value})});
    const j=await r.json();
    $("#out").textContent=JSON.stringify(j,null,2);
    $("#meta").textContent=j.status==="ok"
      ? `${j.tier} · ${j.model||"local"} · ${j.latency_s}s`
      : `error: ${j.error||"see JSON"}`;
  }catch(e){$("#out").textContent=String(e)}
  finally{$("#go").disabled=false}
};
</script></body></html>
"""


class DemoHandler(BaseHTTPRequestHandler):
    server_version = f"TattvaSwarm/{__version__}"

    # -- helpers -----------------------------------------------------------
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict) -> None:
        self._send(code, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _authorized(self) -> bool:
        token = os.environ.get("TATTVA_DEMO_TOKEN", "").strip()
        if not token:
            return True
        return self.headers.get("Authorization", "") == f"Bearer {token}"

    # -- routes ------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/healthz":
            self._json(200, health())
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path != "/api/route":
            self._json(404, {"error": "not found"})
            return
        if not self._authorized():
            self._json(401, {"error": "unauthorized"})
            return
        if not _rate_ok(self.client_address[0]):
            self._json(429, {"error": "rate limit exceeded — try again in a minute"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            self._json(413, {"error": "body too large"})
            return
        raw = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._json(400, {"error": "invalid JSON body"})
            return
        prompt = str(payload.get("prompt", "")).strip()
        if not prompt:
            self._json(400, {"error": "missing required field: prompt"})
            return
        if len(prompt) > MAX_PROMPT:
            self._json(400, {"error": f"prompt too long (max {MAX_PROMPT} chars for the demo)"})
            return
        tier = str(payload.get("tier", "auto"))
        try:
            max_tokens = int(payload.get("max_tokens", DEFAULT_MAX_TOKENS))
        except (TypeError, ValueError):
            max_tokens = DEFAULT_MAX_TOKENS
        max_tokens = max(64, min(max_tokens, MAX_TOKENS_CAP))
        result = route(prompt, tier=tier, max_tokens=max_tokens)
        self._json(200, result)

    def log_message(self, fmt: str, *args) -> None:  # stderr only; stdout stays clean
        sys.stderr.write("[demo] %s - %s\n" % (self.address_string(), fmt % args))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tattva_swarm.demo_server",
                                     description="TattvaSwarm demo HTTP server (stdlib only).")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    load_env_file()
    server = ThreadingHTTPServer((args.host, args.port), DemoHandler)
    sys.stderr.write(f"[demo] TattvaSwarm {__version__} listening on http://{args.host}:{args.port}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
