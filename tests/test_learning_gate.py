"""Tests for the recursive self-improvement gate (learning_gate.py).

Covers the operator-mandated semantics: training pairs are emitted only when
the system failed first and then genuinely resolved (unresolved -> resolved),
stay private per identity, are novel, contain no secrets, and are capped.
"""

import json
import os
import stat

import pytest

from tattva_swarm import learning_gate as lg

GOOD_Q = "How do I configure the TattvaSwarm tier router for a research request?"
GOOD_R = (
    "Route research requests to the research tier: they need external lookup, so "
    "the router forwards them to the MCP research tool and cites the result."
)
FAILED_ATTEMPT = {"tier": "normal", "status": "failed", "note": "misrouted"}


@pytest.fixture(autouse=True)
def _private_home(tmp_path, monkeypatch):
    monkeypatch.setenv("TATTVA_HOME", str(tmp_path / "tattva"))
    return tmp_path


def _episode(question=GOOD_Q, resolution=GOOD_R, attempts=None, **extra):
    ep = {"question": question, "resolution": resolution}
    if attempts is not None:
        ep["attempts"] = attempts
    ep.update(extra)
    return ep


def test_gate_requires_a_learning_event():
    first_try = _episode(attempts=[])
    assert lg.gate_episode(first_try, [], lg.DEFAULT_POLICY) == ("skip", "no_learning_event")

    failed_then_fixed = _episode(attempts=[FAILED_ATTEMPT])
    assert lg.gate_episode(failed_then_fixed, [], lg.DEFAULT_POLICY)[0] == "train"

    flagged = _episode(attempts=[], initially_unresolved=True)
    assert lg.gate_episode(flagged, [], lg.DEFAULT_POLICY)[0] == "train"


def test_emit_pairs_is_idempotent_and_uses_chat_schema():
    lg.record_episode("acme", _episode(attempts=[FAILED_ATTEMPT]))
    first = lg.emit_pairs("acme")
    assert first["emitted"] == 1
    second = lg.emit_pairs("acme")
    assert second["emitted"] == 0  # already emitted; nothing silent duplicated

    pairs = lg.load_pairs("acme")
    assert len(pairs) == 1
    msgs = pairs[0]["messages"]
    assert [m["role"] for m in msgs] == ["system", "user", "assistant"]
    assert msgs[1]["content"] == GOOD_Q
    assert pairs[0]["source"] == "learning-gate/v1"


def test_near_duplicate_question_is_skipped():
    lg.record_episode("acme", _episode(attempts=[FAILED_ATTEMPT]))
    assert lg.emit_pairs("acme")["emitted"] == 1
    paraphrased = _episode(
        question="How do I configure TattvaSwarm tier router for a research request?",
        resolution="Send research traffic to the research tier so the MCP lookup tool answers it.",
        attempts=[FAILED_ATTEMPT],
    )
    lg.record_episode("acme", paraphrased)
    result = lg.emit_pairs("acme")
    assert result["emitted"] == 0
    assert any(s["reason"] == "duplicate_question" for s in result["skipped"])


def test_secret_looking_resolution_is_refused():
    leaky = _episode(
        resolution="Use the key sk-abcdefghijklmnop to sign the request before retrying the call.",
        attempts=[FAILED_ATTEMPT],
    )
    assert lg.gate_episode(leaky, [], lg.DEFAULT_POLICY) == ("skip", "possible_secret")


def test_resolution_too_short_is_skipped():
    tiny = _episode(resolution="ok", attempts=[FAILED_ATTEMPT])
    assert lg.gate_episode(tiny, [], lg.DEFAULT_POLICY) == ("skip", "resolution_too_short")


def test_identity_isolation(tmp_path):
    lg.record_episode("acme", _episode(attempts=[FAILED_ATTEMPT]))
    assert lg.emit_pairs("acme")["emitted"] == 1

    other = lg.run_gate("other-co")
    assert other["pairs"] == 0
    assert other["episodes"] == 0
    assert lg.private_dir("acme") != lg.private_dir("other-co")


def test_daily_cap_limits_emissions():
    for i in range(3):
        q = f"Question number {i}: how do I retry the failed research routing step?"
        lg.record_episode("acme", _episode(question=q, attempts=[FAILED_ATTEMPT]))
    result = lg.emit_pairs("acme", policy={"max_pairs_per_day": 1})
    assert result["emitted"] == 1
    assert any(s["reason"] == "daily_cap_reached" for s in result["skipped"])


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits required")
def test_private_files_use_strict_permissions():
    lg.record_episode("acme", _episode(attempts=[FAILED_ATTEMPT]))
    lg.emit_pairs("acme")
    d = lg.private_dir("acme")
    assert stat.S_IMODE(d.stat().st_mode) == 0o700
    assert stat.S_IMODE((d / "episodes.jsonl").stat().st_mode) == 0o600
    assert stat.S_IMODE((d / "pairs.jsonl").stat().st_mode) == 0o600


def test_record_is_idempotent_and_updates_in_place():
    ep = _episode(attempts=[FAILED_ATTEMPT])
    ep.pop("resolution")
    ep["resolution"] = ""
    first = lg.record_episode("acme", ep)
    assert first.get("stored")
    completed = _episode(attempts=[FAILED_ATTEMPT])
    updated = lg.record_episode("acme", completed)
    assert updated.get("updated")
    episodes = lg.load_episodes("acme")
    assert len(episodes) == 1
    assert episodes[0]["resolution"] == GOOD_R
