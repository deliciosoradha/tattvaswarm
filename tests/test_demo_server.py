"""Demo server tests — pure stdlib, no network, no LLM calls (small tier is local)."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from tattva_swarm import demo_server


@pytest.fixture()
def server(monkeypatch, tmp_path):
    monkeypatch.setenv("TATTVA_HOME", str(tmp_path))
    monkeypatch.setenv("TATTVA_DEMO_RATE_PER_MIN", "0")  # unlimited for tests
    monkeypatch.delenv("TATTVA_DEMO_TOKEN", raising=False)
    # Deterministic "no backend" sandbox: even if the caller's shell exports a
    # real key, this test suite must never reach the network.
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), demo_server.DemoHandler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield srv
    srv.shutdown()
    srv.server_close()


def _url(srv, path: str) -> str:
    return f"http://127.0.0.1:{srv.server_port}{path}"


def _post(srv, payload: dict, headers: dict | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(
        _url(srv, "/api/route"),
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_root_page_serves_html(server):
    with urllib.request.urlopen(_url(server, "/"), timeout=10) as resp:
        body = resp.read().decode("utf-8")
    assert resp.status == 200
    assert "TattvaSwarm" in body
    assert "/api/route" in body


def test_healthz(server):
    with urllib.request.urlopen(_url(server, "/healthz"), timeout=10) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    assert payload["status"] == "ok"
    assert payload["api_key"] in ("set", "missing")


def test_route_small_tier_is_local(server):
    code, payload = _post(server, {"prompt": "hello", "tier": "small"})
    assert code == 200
    assert payload["status"] == "ok"
    assert payload["tier"] == "small"
    assert "local" in payload["reply"].lower()


def test_route_auto_classifies(server):
    code, payload = _post(server, {"prompt": "hello"})
    assert code == 200
    assert payload["tier"] == "normal"  # everyday call, and no key -> honest error
    assert payload["status"] == "error"  # backend missing in this sandboxed test env


def test_bad_json_returns_400(server):
    req = urllib.request.Request(
        _url(server, "/api/route"), data=b"{not json", method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        raise AssertionError("expected HTTPError")
    except urllib.error.HTTPError as exc:
        assert exc.code == 400


def test_missing_prompt_returns_400(server):
    code, payload = _post(server, {"tier": "auto"})
    assert code == 400
    assert "prompt" in payload["error"]


def test_token_gate_when_configured(server, monkeypatch):
    monkeypatch.setenv("TATTVA_DEMO_TOKEN", "sekrit")
    code, _ = _post(server, {"prompt": "hi", "tier": "small"})
    assert code == 401
    code, payload = _post(server, {"prompt": "hi", "tier": "small"},
                          headers={"Authorization": "Bearer sekrit"})
    assert code == 200
    assert payload["status"] == "ok"
