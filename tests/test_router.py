"""Offline tests for the tiered router (no network needed)."""

from tattva_swarm.nebius import TokenFactoryClient
from tattva_swarm.router import classify, route


def test_classify_deterministic():
    assert classify("hola") == classify("hola")


def test_classify_tiers():
    assert classify("Say hello").tier == "normal"
    assert classify("Analyze the trade-offs of this decision").tier == "reasoning"
    assert classify("search the web for the latest news about GPUs").tier == "research"
    long_prompt = "Write a full report and synthesize everything " + "x" * 4200
    assert classify(long_prompt).tier == "heavy"


def test_route_small_local():
    out = route("hola", tier="small")
    assert out["status"] == "ok"
    assert out["model"] is None


def test_route_unknown_tier():
    out = route("hola", tier="nope")
    assert out["status"] == "error"
    assert "unknown tier" in out["error"]


def test_route_backend_error_is_honest():
    client = TokenFactoryClient(api_key="")  # explicitly keyless -> must fail honestly
    out = route("Say hello", tier="normal", client=client)
    assert out["status"] == "error"
    assert "NEBIUS_API_KEY" in out["error"] or "model id" in out["error"]
