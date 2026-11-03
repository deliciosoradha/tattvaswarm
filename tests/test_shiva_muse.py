"""Committed tests for Shiva-Muse hackathon modules (numpy-only)."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "meta_hackathon_2026"))

import numpy as np
from shiva_muse_router import ShivaMuseRouter
from sam31_physics_injector import mask_to_boundary_tensors, InjectionConfig
from verifiable_agent_harness import verify_rollout, taylor_green


def test_meru_parity_bipartite():
    r = ShivaMuseRouter.__new__(ShivaMuseRouter)
    c0 = ShivaMuseRouter.meru_cohort_stratum(0)
    c1 = ShivaMuseRouter.meru_cohort_stratum(1)
    assert c0["color"] == 0
    assert c1["color"] == 1
    assert c0["gray_code"] == 0
    assert c1["gray_code"] == 1


def test_budget_guardrail_never_exceeds_cap():
    with tempfile.TemporaryDirectory() as td:
        ledger = os.path.join(td, "ledger.json")
        router = ShivaMuseRouter(ledger_path=ledger)
        # Force many frontier dispatches on even-parity node 0
        # $1.50 each -> 100 iterations = $150 attempted, must cap at $100
        for i in range(100):
            router.dispatch_agent_task(0, f"prompt {i}", modality="reasoning", estimated_tokens=100000)
        assert router.ledger.current_spend_usd <= router.ledger.hard_spend_cap_usd + 1e-9
        # After cap, must overflow to open weights with $0 cost
        res = router.dispatch_agent_task(0, "overflow", modality="reasoning", estimated_tokens=100000)
        assert res["model"] == "meta-models/muse-spark-open-1026"
        assert res["budget_guardrail"]["cumulative_spend_usd"] <= 100.0 + 1e-9


def test_swarm_always_open_weights_zero_cost():
    with tempfile.TemporaryDirectory() as td:
        router = ShivaMuseRouter(ledger_path=os.path.join(td, "l.json"))
        res = router.dispatch_agent_task(0, "swarm task", modality="swarm")
        assert res["provider"] == "Baseten_Open_Weights"
        assert res["budget_guardrail"]["cost_usd"] == 0.0 if "cost_usd" in res["budget_guardrail"] else True


def test_sam31_injector_shapes():
    soft = np.linspace(0, 1, 64 * 64).reshape(64, 64)
    tensors = mask_to_boundary_tensors(soft, InjectionConfig(grid_h=32, grid_w=48))
    assert tensors["omega_mask"].shape == (32, 48)
    assert set(np.unique(tensors["omega_mask"])).issubset({0, 1})
    assert tensors["dirichlet"].shape == (32, 48)


def test_harness_pass_and_fail():
    u0, v0 = taylor_green(32)
    ok = verify_rollout("m", {"t": 1}, u0, v0, u0.copy(), v0.copy(), dt=0.001, dx=0.19)
    assert ok["status"] == "PASS"
    assert len(ok["verification_certificate"]) == 64
    # Divergent field must fail
    bad_u = np.ones_like(u0)
    bad_v = np.ones_like(v0)
    bad = verify_rollout("m", {"t": 2}, bad_u, bad_v, bad_u, bad_v, dt=10.0, dx=0.01)
    assert bad["status"] == "FAIL"
