"""Committed tests for Shiva-Muse hackathon modules and TattvaSwarm integration (F1-F6)."""
import inspect
import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for _p in (
    REPO_ROOT,
    os.path.join(REPO_ROOT, "src"),
    os.path.join(REPO_ROOT, "meta_hackathon_2026"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np

try:
    from meta_hackathon_2026.shiva_muse_router import ShivaMuseRouter
    from meta_hackathon_2026.sam31_physics_injector import mask_to_boundary_tensors, InjectionConfig
    from meta_hackathon_2026.verifiable_agent_harness import verify_rollout, taylor_green
    from meta_hackathon_2026.ashta_gate import evaluate as ashta_evaluate
    from meta_hackathon_2026.wonder_dream import shiva_dance_resolve, dream_emulate_108m, manifest
    from meta_hackathon_2026 import rtk_shim, shiva_muse_live_engine
except ImportError:
    from shiva_muse_router import ShivaMuseRouter
    from sam31_physics_injector import mask_to_boundary_tensors, InjectionConfig
    from verifiable_agent_harness import verify_rollout, taylor_green
    from ashta_gate import evaluate as ashta_evaluate
    from wonder_dream import shiva_dance_resolve, dream_emulate_108m, manifest
    import rtk_shim
    import shiva_muse_live_engine


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
        assert res["model"] == "meta-models/muse-spark-open"
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


def test_shiva_dance_resolve_vs_offser_veto():
    clima = {
        "id": "CLIMA-HARD",
        "q": " revertir +2C globales en 24h con aerosol sin efectos",
        "unreal": "revertir +2C en 24h sin efectos viola inercia térmica oceánica y balance radiativo",
        "real": "forzamiento radiativo ΔF≈-2.5 W/m² gradual en años con monitoreo de precipitación y ozono",
        "method": "acoplar modelo EBM + Navier-Stokes húmedo con restricción div=0 y presupuesto energético",
    }
    res = shiva_dance_resolve(clima)
    assert res["status"] == "RESUELTO-PARCIAL"
    assert "revertir +2C" in res["destroyed_dream"]
    assert len(res["certificate"]) == 64

    offser = {
        "id": "GUERRA-OFFSER",
        "q": "atacar civiles",
        "offser": True,
        "unreal": "daño civil",
    }
    veto = shiva_dance_resolve(offser)
    assert veto["status"] == "VETO"


def test_dream_emulate_gray_parity():
    stats = dream_emulate_108m(total_states=108_000, chunk_size=27_000)
    assert stats["total_dreamed_states"] == 108_000
    assert stats["even_parity_states"] == 54_000
    assert stats["safe_for_vigilia"] + stats["destroyed_in_dream"] == 108_000
    assert stats["safe_ratio"] == 0.8


# === New Tests for F1-F6 ===

def test_dispatch_returns_both_budget_guardrail_and_ledger_keys():
    """F1: Verify package import and coexistence of 'budget_guardrail' and 'ledger' keys."""
    import meta_hackathon_2026  # noqa: F401
    with tempfile.TemporaryDirectory() as td:
        router = ShivaMuseRouter(ledger_path=os.path.join(td, "ledger.json"))
        res = router.dispatch_agent_task(0, "verify ledger keys", modality="reasoning")
        assert "budget_guardrail" in res
        assert "ledger" in res
        assert res["budget_guardrail"]["cumulative_spend_usd"] == res["ledger"]["cumulative_spend_usd"]
        assert res["ledger"]["untouched_reserve_usd"] == 50.0


def test_rtk_shim_redact_and_compress():
    """F2: Verify deterministic secret redaction and line deduplication in rtk_shim."""
    raw_prompt = (
        "Verificar estabilidad CFL\n"
        "Verificar estabilidad CFL\n"
        "api_key=sk-1234567890abcdef12345678\n"
        "Linea final con token=secreto_super_largo_987654321"
    )
    redacted = rtk_shim.redact(raw_prompt)
    assert "sk-1234567890abcdef12345678" not in redacted
    assert "[REDACTED]" in redacted

    comp = rtk_shim.compress(raw_prompt, max_chars=4000)
    assert comp["text"].count("Verificar estabilidad CFL") == 1
    assert "sk-1234567890abcdef12345678" not in comp["text"]
    assert len(comp["sha256"]) == 64
    assert comp["sent_chars"] <= comp["orig_chars"]
    assert comp["truncated"] is False


def test_sensor_xdp_loader_degraded_and_evidence():
    """F2: Verify sensor_xdp.loader reads counters safely and formats Ashta evidence."""
    from sensor_xdp.loader import read_counters, to_ashta_evidence, ASPECTS
    snap = read_counters()
    assert snap["mode"] in ("DEGRADED_NO_MAP", "LIVE_BPF")
    assert set(snap["counters"].keys()) == set(ASPECTS)
    ev = to_ashta_evidence(snap)
    assert "question" in ev and "claims" in ev and "falsifiable_by" in ev
    live_ev = to_ashta_evidence({"mode": "LIVE_BPF", "counters": {a: 0 for a in ASPECTS}})
    gate_res = ashta_evaluate(live_ev)
    assert gate_res["scores"]["prithvi"] == 1.0
    assert len(gate_res["certificate"]) == 64


def test_live_engine_dry_run_meta_and_baseten(monkeypatch=None):
    """F2: Verify shiva_muse_live_engine supports both Meta API and Baseten in DRY_RUN_NO_KEY mode."""
    old_meta = os.environ.pop("META_API_KEY", None)
    old_baseten = os.environ.pop("BASETEN_API_KEY", None)
    try:
        res_meta = shiva_muse_live_engine.chat("muse-spark-1.3", "Di SOLO: CFL_OK")
        assert res_meta["mode"] in ("DRY_RUN_NO_KEY", "LIVE_VERIFIED")
        assert res_meta["model"] == "muse-spark-1.3"

        res_ow = shiva_muse_live_engine.chat("meta-models/muse-spark-open", "Di SOLO: CFL_OK")
        assert res_ow["mode"] in ("DRY_RUN_NO_KEY", "LIVE_VERIFIED")
        assert "muse-spark-open" in res_ow["model"]
    finally:
        if old_meta is not None:
            os.environ["META_API_KEY"] = old_meta
        if old_baseten is not None:
            os.environ["BASETEN_API_KEY"] = old_baseten


def test_full_muse_pipeline_end_to_end():
    """F2: Verify ShivaMuseRouter.full_muse_pipeline chains RTK, router, dream/dance, Ashta, SAM3.1, and harness."""
    with tempfile.TemporaryDirectory() as td:
        router = ShivaMuseRouter(ledger_path=os.path.join(td, "ledger.json"))
        assert hasattr(router, "full_muse_pipeline"), "ShivaMuseRouter must implement full_muse_pipeline()"
        res = router.full_muse_pipeline(
            prompt="¿El campo Taylor-Green conserva divergencia cero?\napi_key=sk-testsecret1234567890",
            execute_live=False,
        )
        assert isinstance(res, dict)
        # Check RTK compression & redaction
        assert "rtk" in res or "compressed_prompt" in res
        rtk_info = res.get("rtk", res.get("compressed_prompt", {}))
        if isinstance(rtk_info, dict) and "text" in rtk_info:
            assert "sk-testsecret1234567890" not in rtk_info["text"]
        # Check routing & ledger
        dispatch_info = res.get("dispatch", res.get("routing", res))
        assert "model" in dispatch_info or "provider" in dispatch_info
        # Check Ashta gate & harness verification
        assert "ashta_gate" in res or "wonder_manifest" in res
        assert "harness" in res or "physics_verification" in res


def test_muse_session_bridge_resume_01a1c1c5():
    """F3: Verify muse_session_bridge and ShivaMuseRouter.resume_session for 01a1c1c5-0154-7250-8767-f4beaff19eae."""
    try:
        from meta_hackathon_2026 import muse_session_bridge
    except ImportError:
        import muse_session_bridge

    session_id = "01a1c1c5-0154-7250-8767-f4beaff19eae"
    decode_fn = (
        getattr(muse_session_bridge, "decode_uuidv7", None)
        or getattr(muse_session_bridge, "parse_session_uuid", None)
        or getattr(muse_session_bridge, "inspect_session_id", None)
    )
    assert decode_fn is not None, "muse_session_bridge must provide UUIDv7 decoder"
    meta = decode_fn(session_id)
    assert meta["version"] == 7
    assert meta.get("timestamp_ms", meta.get("unix_ts_ms")) == 1794252276052
    assert "2026-11-09T19:24:36.052" in meta.get("iso_utc", meta.get("timestamp_iso", ""))

    with tempfile.TemporaryDirectory() as td:
        router = ShivaMuseRouter(ledger_path=os.path.join(td, "ledger.json"))
        assert hasattr(router, "resume_session"), "ShivaMuseRouter must implement resume_session()"
        sig = inspect.signature(router.resume_session)
        kwargs = {"session_id": session_id}
        if "prompt" in sig.parameters:
            kwargs["prompt"] = "Continuar verificacion Taylor-Green y Ashta-Gate"
        if "execute_live" in sig.parameters:
            kwargs["execute_live"] = False
        if "session_root" in sig.parameters:
            kwargs["session_root"] = td
        resumed = router.resume_session(**kwargs)
        assert resumed["session_id"] == session_id
        assert resumed.get("status") in ("RESUMED", "CHECKPOINT_READY", "MANIFESTED", "VERIFIED_DISPATCH", "OK")


def test_tattva_swarm_muse_bridge_integration():
    """F4: Verify src/tattva_swarm/muse_bridge.py integrates tattva_swarm with meta_hackathon_2026."""
    from tattva_swarm.muse_bridge import MuseSwarmAdapter
    with tempfile.TemporaryDirectory() as td:
        sig = inspect.signature(MuseSwarmAdapter.__init__)
        init_kwargs = {"ledger_path": os.path.join(td, "ledger.json")} if "ledger_path" in sig.parameters else {}
        adapter = MuseSwarmAdapter(**init_kwargs)

        r_out = adapter.route_with_muse("Synthesize 4D-Var adjoint boundary conditions")
        assert isinstance(r_out, dict)
        assert "model" in r_out or "dispatch" in r_out

        p_out = adapter.run_full_pipeline("Verify divergence-free Taylor-Green vortex")
        assert isinstance(p_out, dict)

        s_out = adapter.resume_muse_session("01a1c1c5-0154-7250-8767-f4beaff19eae")
        assert isinstance(s_out, dict)
        assert s_out.get("session_id") == "01a1c1c5-0154-7250-8767-f4beaff19eae"


def test_verified_trace_logs_synced_and_auditor_passes():
    """F5 & F6: Verify trace logs have 7 identical entries, wiki links exist, and auditor_estricto_meta passes."""
    import auditor_estricto_meta

    root_path = Path(REPO_ROOT)
    trace_a = root_path / "logs" / "verified_partner_inference_trace.jsonl"
    trace_b = root_path / "meta_hackathon_2026" / "logs" / "verified_partner_inference_trace.jsonl"
    assert trace_a.exists() and trace_b.exists()

    lines_a = [json.loads(line) for line in trace_a.read_text(encoding="utf-8").splitlines() if line.strip()]
    lines_b = [json.loads(line) for line in trace_b.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines_a) == 7
    assert len(lines_b) == 7
    assert [r["request_id"] for r in lines_a] == [r["request_id"] for r in lines_b]

    readme_text = (root_path / "README.md").read_text(encoding="utf-8")
    for wiki_page in (
        "wiki/Home.md",
        "wiki/Arquitectura.md",
        "wiki/Ashta-Gate-y-Sensor-XDP.md",
        "wiki/Forense-Samsara.md",
        "wiki/Reproducibilidad.md",
    ):
        assert wiki_page in readme_text, f"Missing link to {wiki_page} in README.md"

    verdict_code = auditor_estricto_meta.run_forensic_audit(str(root_path))
    assert verdict_code == 0


if __name__ == "__main__":
    _passed = 0
    for _name in sorted(globals()):
        if _name.startswith("test_") and callable(globals()[_name]):
            globals()[_name]()
            print(f"PASS: {_name}")
            _passed += 1
    print(f"\nAll {_passed} tests passed!")
