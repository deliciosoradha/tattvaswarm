"""MCP server protocol tests — pure stdlib, no network, no Docker."""

from __future__ import annotations

import json

from tattva_swarm import mcp_server

ALL_TOOLS = {
    "tattva_status",
    "tattva_route",
    "tattva_memory_add",
    "tattva_memory_search",
    "tattva_swarm_run",
    "tattva_code_run",
}


def test_initialize():
    resp = mcp_server.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert resp["result"]["protocolVersion"] == mcp_server.PROTOCOL_VERSION
    assert resp["result"]["serverInfo"]["name"] == "tattvaswarm"
    assert "tools" in resp["result"]["capabilities"]


def test_tools_list():
    resp = mcp_server.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tools = resp["result"]["tools"]
    assert {t["name"] for t in tools} == ALL_TOOLS
    for tool in tools:
        assert tool["inputSchema"]["type"] == "object"
        assert tool["description"]


def test_notification_returns_none():
    assert mcp_server.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_unknown_method_is_error():
    resp = mcp_server.handle_message({"jsonrpc": "2.0", "id": 3, "method": "bogus/method"})
    assert resp["error"]["code"] == -32601


def test_ping():
    resp = mcp_server.handle_message({"jsonrpc": "2.0", "id": 4, "method": "ping"})
    assert resp["result"] == {}


def _call(name: str, arguments: dict) -> tuple[dict, bool]:
    resp = mcp_server.handle_message(
        {"jsonrpc": "2.0", "id": 99, "method": "tools/call",
         "params": {"name": name, "arguments": arguments}}
    )
    result = resp["result"]
    payload = json.loads(result["content"][0]["text"])
    return payload, bool(result["isError"])


def test_status_without_key_is_honest(monkeypatch, tmp_path):
    monkeypatch.setenv("TATTVA_HOME", str(tmp_path))
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    payload, is_err = _call("tattva_status", {})
    assert is_err is False
    assert payload["api_key"].startswith("missing")
    assert set(payload["tiers"]) == {"normal", "reasoning", "heavy"}


def test_memory_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("TATTVA_HOME", str(tmp_path))
    added, err1 = _call("tattva_memory_add", {"text": "sovereign swarm test entry", "tags": ["t"]})
    assert err1 is False and added["status"] == "ok" and added["id"] >= 1
    found, err2 = _call("tattva_memory_search", {"query": "sovereign swarm"})
    assert err2 is False and found["count"] >= 1


def test_code_run_requires_command():
    payload, is_err = _call("tattva_code_run", {})
    assert is_err is True
    assert "command" in payload["error"]


def test_swarm_run_small():
    payload, is_err = _call("tattva_swarm_run", {"workers": 2000, "steps": 5})
    assert is_err is False
    assert payload["workers"] == 2000
    assert payload["implementation"] in ("rust", "python")
    assert payload["deterministic"] is True
