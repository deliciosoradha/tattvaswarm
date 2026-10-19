"""Tests for the optional LangChain adapter (skipped when the extra is absent)."""

import json

import pytest

pytest.importorskip("langchain_core")

from tattva_swarm import langchain_adapter as la  # noqa: E402


def test_tools_present():
    names = {tool.name for tool in la.get_tools()}
    assert {
        "tattva_route",
        "tattva_memory_add",
        "tattva_memory_search",
        "tattva_swarm_run",
        "tattva_code_run",
    } <= names


def test_chat_invoke_uses_router(monkeypatch):
    def fake_route(prompt, *, tier="auto", temperature=0.0, max_tokens=None):
        return {
            "status": "ok",
            "tier": "normal",
            "model": "fake-model",
            "reply": f"echo:{prompt}",
            "usage": {"total_tokens": 3},
            "latency_s": 0.01,
        }

    monkeypatch.setattr(la, "route", fake_route)
    llm = la.ChatTattvaSwarm()
    message = llm.invoke([("human", "hola")])
    assert message.content == "echo:hola"
    assert message.additional_kwargs["tattva"]["tier"] == "normal"


def test_chat_error_is_honest(monkeypatch):
    def bad_route(prompt, **kwargs):
        return {"status": "error", "tier": "normal", "error": "backend missing", "http_status": 401}

    monkeypatch.setattr(la, "route", bad_route)
    llm = la.ChatTattvaSwarm()
    with pytest.raises(RuntimeError, match="backend missing"):
        llm.invoke([("human", "hola")])


def test_tool_route_returns_json(monkeypatch):
    def fake_route(prompt, *, tier="auto"):
        return {"status": "ok", "tier": tier, "reply": "x"}

    monkeypatch.setattr(la, "route", fake_route)
    out = json.loads(la._tool_route("hello", tier="heavy"))
    assert out["tier"] == "heavy"
