"""Tests for the logical swarm engine (determinism + sane report)."""

from tattva_swarm.engine import SwarmConfig, run_swarm


def test_determinism_and_solves():
    cfg = SwarmConfig(workers=20_000, steps=6, seed=7)
    a = run_swarm(cfg)
    b = run_swarm(cfg)
    assert a.checksum == b.checksum
    assert a.solves == b.solves
    assert a.workers == 20_000
    assert a.solves > 0
    assert 0 <= a.converged <= a.workers


def test_report_shape():
    rep = run_swarm(SwarmConfig(workers=1_000, steps=4))
    d = rep.to_dict()
    assert d["residual"] == d["workers"] - d["converged"]
    assert d["deterministic"] is True
    assert isinstance(d["checksum"], str)


def test_invalid_config_rejected():
    import pytest

    with pytest.raises(ValueError):
        SwarmConfig(workers=0)
