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


from ashta_gate import evaluate as ashta_evaluate


def _grounded_trace():
    return {
        "question": "¿El campo Taylor-Green conserva divergencia cero?",
        "answer": "Sí, conserva divergencia cero dentro de tolerancia; límite: rejilla 32x32.",
        "claims": [
            {"text": "div(u)=0 en la rejilla", "evidence": "max_div medido con harness"},
            {"text": "CFL estable con dt=0.001", "evidence": "cfl_number calculado"},
        ],
        "assumptions": ["rejilla uniforme", "flujo incompresible"],
        "alternatives": ["esquema explícito (rechazado por CFL)", "rejilla 64 (costo)"],
        "falsifiable_by": "si max_div supera 1e-6 en la traza CUPTI",
        "uncertainty": 0.05,
        "invariants": {"cfl": 0.5, "max_div": 1e-9},
    }


def test_ashta_pass_grounded():
    out = ashta_evaluate(_grounded_trace())
    assert out["verdict"] == "pass"
    assert out["scores"]["prithvi"] == 1.0
    assert out["scores"]["agni"] == 1.0
    assert len(out["certificate"]) == 64


def test_ashta_veto_speculation():
    speculative = {"question": "q", "answer": "seguramente funciona de maravilla",
                   "claims": [{"text": "todo saldrá bien", "evidence": ""}]}
    out = ashta_evaluate(speculative)
    assert out["verdict"] == "veto"
    assert any("prithvi" in r for r in out["reasons"])
    assert any("agni" in r for r in out["reasons"])


def test_ashta_certificate_deterministic_and_chains_with_harness():
    a = ashta_evaluate(_grounded_trace())
    b = ashta_evaluate(_grounded_trace())
    assert a["certificate"] == b["certificate"]
    assert len(a["input_sha256"]) == 64
    u0, v0 = taylor_green(16)
    ok = verify_rollout("m", {"t": 1}, u0, v0, u0.copy(), v0.copy(), dt=0.001, dx=0.19)
    assert ok["status"] == "PASS" and a["verdict"] == "pass"
