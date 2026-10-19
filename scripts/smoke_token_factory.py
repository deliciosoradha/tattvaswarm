#!/usr/bin/env python3
"""Token Factory smoke test — stdlib only (runs before `pip install`).

What it does:
  1. loads NEBIUS_API_KEY / NEBIUS_BASE_URL from env or a local .env
  2. GET /v1/models  -> verifies the key, lists models (NVIDIA ones marked)
  3. optionally runs one chat completion against a chosen model

Honest by design: prints the exact HTTP status and error body on failure.
Never prints the API key.

Usage:
  python scripts/smoke_token_factory.py --list-models
  python scripts/smoke_token_factory.py --model <id> --prompt "Reply with exactly: TATTVA_OK"
  python scripts/smoke_token_factory.py --all --out evidence/smoke_YYYYmmdd.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"


def load_dotenv(path: Path = Path(".env")) -> None:
    """Minimal .env loader (no dependencies). Does not override real env vars."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def api_request(base_url: str, key: str, endpoint: str, payload: dict | None = None, timeout: int = 60) -> tuple[int, dict | str]:
    url = base_url.rstrip("/") + endpoint
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    req.add_header("Authorization", f"Bearer {key}")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status = resp.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        status = exc.code
    except Exception as exc:  # noqa: BLE001 — surface the exact failure, honestly
        return -1, f"{type(exc).__name__}: {exc}"
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        parsed = body
    return status, parsed


def main() -> int:
    parser = argparse.ArgumentParser(description="Nebius Token Factory smoke test")
    parser.add_argument("--list-models", action="store_true", help="list models from GET /v1/models")
    parser.add_argument("--model", default=os.environ.get("TATTVA_MODEL_FAST", ""), help="model id for the chat test")
    parser.add_argument("--prompt", default="Reply with exactly: TATTVA_OK")
    parser.add_argument("--max-tokens", type=int, default=32)
    parser.add_argument("--all", action="store_true", help="list models AND run the chat test")
    parser.add_argument("--out", default="", help="write raw evidence JSON to this path")
    args = parser.parse_args()

    load_dotenv()
    key = os.environ.get("NEBIUS_API_KEY", "").strip()
    base_url = os.environ.get("NEBIUS_BASE_URL", "").strip() or DEFAULT_BASE_URL

    if not key:
        print("[FAIL] NEBIUS_API_KEY is not set (env or .env). Get one at https://tokenfactory.nebius.com/")
        return 2
    print(f"[ok] key present (len={len(key)}), base_url={base_url}")

    evidence: dict = {"base_url": base_url, "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    exit_code = 0

    if args.list_models or args.all:
        status, body = api_request(base_url, key, "/models")
        print(f"[models] GET /models -> HTTP {status}")
        evidence["models_http_status"] = status
        if status == 200 and isinstance(body, dict):
            ids = sorted(m.get("id", "?") for m in body.get("data", []))
            nvidia = [i for i in ids if i.lower().startswith("nvidia/") or "nemotron" in i.lower()]
            print(f"[models] total={len(ids)} · nvidia/nemotron={len(nvidia)}")
            for i in ids:
                mark = " <-- NVIDIA" if i in nvidia else ""
                print(f"   - {i}{mark}")
            evidence["models_total"] = len(ids)
            evidence["nvidia_models"] = nvidia
        else:
            print(f"[models] body: {str(body)[:400]}")
            evidence["models_body"] = body
            exit_code = 1

    if args.all or args.model:
        if not args.model:
            print("[warn] no --model given and TATTVA_MODEL_FAST is empty — skipping chat test")
        else:
            payload = {
                "model": args.model,
                "messages": [{"role": "user", "content": args.prompt}],
                "max_tokens": args.max_tokens,
                "temperature": 0,
            }
            t0 = time.monotonic()
            status, body = api_request(base_url, key, "/chat/completions", payload, timeout=120)
            latency = round(time.monotonic() - t0, 3)
            print(f"[chat] POST /chat/completions ({args.model}) -> HTTP {status} in {latency}s")
            evidence["chat"] = {"model": args.model, "http_status": status, "latency_s": latency}
            if status == 200 and isinstance(body, dict):
                text = body.get("choices", [{}])[0].get("message", {}).get("content", "")
                usage = body.get("usage", {})
                print(f"[chat] reply: {text!r}")
                print(f"[chat] usage: {usage}")
                evidence["chat"]["reply"] = text
                evidence["chat"]["usage"] = usage
            else:
                print(f"[chat] body: {str(body)[:400]}")
                evidence["chat"]["body"] = body
                exit_code = 1

    evidence["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    evidence["exit_code"] = exit_code
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[ok] evidence written: {out_path}")

    print(f"[done] exit={exit_code}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
