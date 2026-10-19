"""Qdrant context provider (stdlib only, read-only) — our RAG store, included.

The local Qdrant (:6333) holds two working collections:

- ``radhika_hotcontext`` — hot context cards (kanban/telemetry, title+body payloads)
- ``radhika_live_context`` — live context notes

This module is a *context provider* for the swarm: it reads recent cards and can
filter them locally by keyword. Vector search is available (``search``) and the
API contract is ready, but the original 2048-dim embedder was retired, so
text->vector embedding is a separate (planned) migration — callers can pass an
already-computed vector today.

Configuration (environment only, never hardcoded, never printed):
- ``QDRANT_URL``      default ``http://localhost:6333``
- ``QDRANT_API_KEY``  optional api-key header (the local instance uses one)

CLI:
    python3 -m tattva_swarm.qdrant_context status
    python3 -m tattva_swarm.qdrant_context recent --limit 5
    python3 -m tattva_swarm.qdrant_context match "rst_flood" --limit 5
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_COLLECTION = "radhika_hotcontext"


def _base_url() -> str:
    return os.environ.get("QDRANT_URL", "http://localhost:6333").rstrip("/")


def _headers() -> dict:
    headers = {"Content-Type": "application/json"}
    key = os.environ.get("QDRANT_API_KEY") or ""
    if key:
        headers["api-key"] = key
    return headers


def _request(method: str, path: str, payload: dict | None = None, timeout: float = 10.0) -> dict:
    request = urllib.request.Request(
        _base_url() + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method,
    )
    for name, value in _headers().items():
        request.add_header(name, value)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"qdrant unreachable at {_base_url()}: {exc}") from exc


def status() -> dict:
    collections = _request("GET", "/collections").get("result", {}).get("collections", [])
    out = []
    for entry in collections:
        name = entry.get("name")
        try:
            info = _request("GET", f"/collections/{name}").get("result", {})
            out.append({"name": name, "points_count": info.get("points_count"), "status": info.get("status")})
        except RuntimeError as exc:
            out.append({"name": name, "error": str(exc)})
    return {"url": _base_url(), "collections": out}


def recent(collection: str = DEFAULT_COLLECTION, limit: int = 10) -> list[dict]:
    result = _request(
        "POST",
        f"/collections/{collection}/points/scroll",
        {"limit": int(limit), "with_payload": True, "with_vector": False},
    )
    return result.get("result", {}).get("points", [])


def summarize(point: dict, max_chars: int = 400) -> dict:
    payload = point.get("payload") or {}
    text = " ".join(str(payload.get(field, "")) for field in ("title", "body") if payload.get(field))
    return {
        "id": point.get("id"),
        "task_id": payload.get("task_id", ""),
        "status": payload.get("status", ""),
        "title": payload.get("title", ""),
        "snippet": text[:max_chars],
    }


def match(query: str, collection: str = DEFAULT_COLLECTION, limit: int = 5, scan: int = 400) -> list[dict]:
    """Keyword match over recent cards (local, case-insensitive)."""
    needle = (query or "").lower().strip()
    if not needle:
        return []
    hits: list[dict] = []
    for point in recent(collection, scan):
        text = json.dumps(point.get("payload") or {}, ensure_ascii=False).lower()
        if needle in text:
            hits.append(summarize(point))
            if len(hits) >= limit:
                break
    return hits


def search(collection: str, vector: list[float], limit: int = 5) -> list[dict]:
    result = _request(
        "POST",
        f"/collections/{collection}/points/search",
        {"vector": [float(v) for v in vector], "limit": int(limit), "with_payload": True},
    )
    return result.get("result", [])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tattva_swarm.qdrant_context", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status")
    p_recent = sub.add_parser("recent")
    p_recent.add_argument("--collection", default=DEFAULT_COLLECTION)
    p_recent.add_argument("--limit", type=int, default=10)
    p_match = sub.add_parser("match")
    p_match.add_argument("query")
    p_match.add_argument("--collection", default=DEFAULT_COLLECTION)
    p_match.add_argument("--limit", type=int, default=5)
    p_search = sub.add_parser("search")
    p_search.add_argument("--collection", required=True)
    p_search.add_argument("--vector", required=True, help="JSON array of floats")
    p_search.add_argument("--limit", type=int, default=5)

    args = parser.parse_args(argv)
    try:
        if args.cmd == "status":
            result: object = status()
        elif args.cmd == "recent":
            result = [summarize(p) for p in recent(args.collection, args.limit)]
        elif args.cmd == "match":
            result = match(args.query, args.collection, args.limit)
        else:
            result = search(args.collection, json.loads(args.vector), args.limit)
    except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
