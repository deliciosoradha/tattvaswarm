"""Offline tests for the Qdrant context provider (no server required)."""

import pytest

from tattva_swarm import qdrant_context as qc

FAKE_POINTS = [
    {
        "id": 1,
        "payload": {
            "task_id": "t_1",
            "status": "ready",
            "title": "[telemetry] rst_flood dst_port=8703 (sev high)",
            "body": "Sensor XDP observed a rst_flood event on port 8703 with severity high.",
        },
    },
    {
        "id": 2,
        "payload": {
            "task_id": "t_2",
            "status": "todo",
            "title": "MC-FASE4: Oracle ARM64",
            "body": "Provision a VM.Standard.A1.Flex within Always Free and validate builds.",
        },
    },
]


def test_summarize_builds_snippet_and_truncates():
    point = {"id": 9, "payload": {"title": "T", "body": "x" * 500, "status": "ready", "task_id": "t_9"}}
    out = qc.summarize(point, max_chars=100)
    assert out["id"] == 9 and out["task_id"] == "t_9" and out["status"] == "ready"
    assert out["title"] == "T"
    assert len(out["snippet"]) == 100


def test_match_filters_locally_and_respects_limit(monkeypatch):
    monkeypatch.setattr(qc, "recent", lambda collection, limit: FAKE_POINTS[:limit])
    hits = qc.match("RST_FLOOD")
    assert len(hits) == 1
    assert hits[0]["task_id"] == "t_1"
    assert qc.match("oracle arm64") [0]["task_id"] == "t_2"
    assert qc.match("nothing-matches-this") == []


def test_match_empty_query_returns_nothing(monkeypatch):
    monkeypatch.setattr(qc, "recent", lambda collection, limit: FAKE_POINTS)
    assert qc.match("") == []


def test_status_shapes(monkeypatch):
    def fake_request(method, path, payload=None, timeout=10.0):
        if path == "/collections":
            return {"result": {"collections": [{"name": "radhika_hotcontext"}]}}
        return {"result": {"points_count": 148, "status": "green"}}

    monkeypatch.setattr(qc, "_request", fake_request)
    out = qc.status()
    assert out["collections"] == [{"name": "radhika_hotcontext", "points_count": 148, "status": "green"}]


@pytest.mark.skipif(not qc.os.environ.get("TATTVA_TEST_QDRANT"), reason="local qdrant opt-in test")
def test_live_status_reaches_local_qdrant():
    out = qc.status()
    assert any(c.get("name") == "radhika_hotcontext" for c in out["collections"])
