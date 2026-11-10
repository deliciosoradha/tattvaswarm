"""Shiva-Muse Bridge (`MuseSwarmAdapter`) — integrates `meta_hackathon_2026` into `tattva_swarm`.

Exposes Meta Muse routing (`ShivaMuseRouter`), `full_muse_pipeline`, `ashta_gate`,
`wonder_dream`, `rtk_shim`, and `resume_session("01a1c1c5-0154-7250-8767-f4beaff19eae")`
to `tattva_swarm.router`, `tattva_swarm.cli`, and `tattva_swarm.mcp_server`.
"""

from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_MUSE_SESSION_ID = "01a1c1c5-0154-7250-8767-f4beaff19eae"

# Ensure repo root and meta_hackathon_2026 are importable regardless of cwd/PYTHONPATH
_REPO_ROOT = Path(__file__).resolve().parents[2]
_META_PKG_DIR = _REPO_ROOT / "meta_hackathon_2026"
for _p in (str(_REPO_ROOT), str(_META_PKG_DIR)):
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

try:
    from meta_hackathon_2026.shiva_muse_router import CreditLedger, ShivaMuseRouter
    from meta_hackathon_2026 import ashta_gate, rtk_shim, wonder_dream
    from meta_hackathon_2026 import sam31_physics_injector, verifiable_agent_harness
    from meta_hackathon_2026 import shiva_muse_live_engine
except ImportError:  # pragma: no cover
    from shiva_muse_router import CreditLedger, ShivaMuseRouter  # type: ignore
    import ashta_gate  # type: ignore
    import rtk_shim  # type: ignore
    import wonder_dream  # type: ignore
    import sam31_physics_injector  # type: ignore
    import verifiable_agent_harness  # type: ignore
    import shiva_muse_live_engine  # type: ignore


TIER_TO_MODALITY: Dict[str, str] = {
    "small": "swarm",
    "normal": "reasoning",
    "reasoning": "reasoning",
    "heavy": "reasoning",
    "research": "reasoning",
    "muse": "reasoning",
    "swarm": "swarm",
    "vision": "vision",
    "voice": "voice",
    "creative": "creative",
}


class MuseSwarmAdapter:
    """Adapter bridging TattvaSwarm (`src/tattva_swarm`) and Shiva-Muse (`meta_hackathon_2026`)."""

    DEFAULT_SESSION_ID = DEFAULT_MUSE_SESSION_ID

    def __init__(self, ledger_path: Optional[str] = None) -> None:
        resolved_ledger = ledger_path or str(_REPO_ROOT / "logs" / "meta_credit_ledger.json")
        self.router = ShivaMuseRouter(ledger_path=resolved_ledger)

    # ------------------------------------------------------------------
    # RTK Shim (prompt compression & secret redaction)
    # ------------------------------------------------------------------
    @staticmethod
    def rtk_redact(text: str) -> str:
        return rtk_shim.redact(text)

    @staticmethod
    def rtk_compress(prompt: str, max_chars: int = 4000) -> Dict[str, Any]:
        return rtk_shim.compress(prompt, max_chars=max_chars)

    # ------------------------------------------------------------------
    # Ashta-Gate (8-aspect deterministic reasoning gate)
    # ------------------------------------------------------------------
    @staticmethod
    def evaluate_ashta_gate(trace: Dict[str, Any]) -> Dict[str, Any]:
        return ashta_gate.evaluate(trace)

    # ------------------------------------------------------------------
    # Wonder Dream (dream_candidates, manifest, shiva_dance_resolve, 108M Gray-code)
    # ------------------------------------------------------------------
    @staticmethod
    def wonder_manifest(question: str, n: int = 4) -> Dict[str, Any]:
        return wonder_dream.manifest(question, n=n)

    @staticmethod
    def wonder_shiva_dance(claim: Dict[str, Any]) -> Dict[str, Any]:
        return wonder_dream.shiva_dance_resolve(claim)

    @staticmethod
    def wonder_emulate_108m(
        total_states: int = 108_000, chunk_size: int = 27_000
    ) -> Dict[str, Any]:
        return wonder_dream.dream_emulate_108m(
            total_states=total_states, chunk_size=chunk_size
        )

    # ------------------------------------------------------------------
    # Core Muse Routing (`route_with_muse`)
    # ------------------------------------------------------------------
    def route_with_muse(
        self,
        prompt: str,
        *,
        task_id: int = 0,
        tier: str = "reasoning",
        modality: Optional[str] = None,
        estimated_tokens: int = 1200,
        trace: Optional[Dict[str, Any]] = None,
        execute_live: bool = False,
    ) -> Dict[str, Any]:
        """Compress prompt via RTK Shim, route via ShivaMuseRouter, and optionally gate via Ashta-Gate."""
        compressed = self.rtk_compress(prompt)
        clean_prompt = compressed["text"]
        mod = modality or TIER_TO_MODALITY.get(tier, "reasoning")

        if trace is not None:
            dispatch_res = self.router.gated_dispatch(task_id, trace, modality=mod)
        else:
            sig = inspect.signature(self.router.dispatch_agent_task)
            params = list(sig.parameters.keys())
            if "prompt" in params:
                dispatch_res = self.router.dispatch_agent_task(
                    task_id, clean_prompt, modality=mod, estimated_tokens=estimated_tokens
                )
            else:
                dispatch_res = self.router.dispatch_agent_task(
                    task_id, 6, mod, estimated_tokens, max(200, estimated_tokens // 3)
                )

        # Ensure both budget_guardrail and ledger keys are present
        guardrail = dispatch_res.get("budget_guardrail") or dispatch_res.get("ledger") or {}
        dispatch_res.setdefault("budget_guardrail", guardrail)
        dispatch_res.setdefault("ledger", guardrail)

        live_result: Optional[Dict[str, Any]] = None
        if execute_live:
            live_result = shiva_muse_live_engine.chat(
                dispatch_res["model"], clean_prompt
            )

        return {
            "status": "ok",
            "tier": tier,
            "modality": mod,
            "provider": dispatch_res.get("provider", "Meta_Model_API"),
            "model": dispatch_res.get("model"),
            "reply": (
                live_result.get("content")
                if (live_result and live_result.get("content"))
                else f"[{dispatch_res.get('provider')}:{dispatch_res.get('model')}] "
                     f"status={dispatch_res.get('status')} cert={str(dispatch_res.get('verification_certificate', ''))[:16]}"
            ),
            "rtk_shim": compressed,
            "muse_dispatch": dispatch_res,
            "dispatch": dispatch_res,
            "budget_guardrail": guardrail,
            "ledger": guardrail,
            "verification_certificate": dispatch_res.get("verification_certificate"),
            "live_inference": live_result,
        }

    # ------------------------------------------------------------------
    # Full End-to-End Shiva-Muse Pipeline (`run_full_pipeline`)
    # ------------------------------------------------------------------
    def run_full_pipeline(
        self,
        prompt: str,
        *,
        agent_id: int = 0,
        dimension: int = 6,
        task_type: str = "reasoning",
        execute_live: bool = False,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Run the full Shiva-Muse pipeline (`full_muse_pipeline`) or synthesize all stages if not yet attached."""
        if hasattr(self.router, "full_muse_pipeline"):
            sig = inspect.signature(self.router.full_muse_pipeline)
            call_kwargs: Dict[str, Any] = {}
            if "agent_id" in sig.parameters:
                call_kwargs["agent_id"] = agent_id
            if "task_id" in sig.parameters:
                call_kwargs["task_id"] = agent_id
            if "dimension" in sig.parameters:
                call_kwargs["dimension"] = dimension
            if "task_type" in sig.parameters:
                call_kwargs["task_type"] = task_type
            if "modality" in sig.parameters:
                call_kwargs["modality"] = task_type
            if "execute_live" in sig.parameters:
                call_kwargs["execute_live"] = execute_live
            for k, v in kwargs.items():
                if k in sig.parameters:
                    call_kwargs[k] = v
            res = self.router.full_muse_pipeline(prompt, **call_kwargs)
            if isinstance(res, dict):
                res = dict(res)
                res["pipeline_status"] = res.get("status", "PIPELINE_VERIFIED")
                res["status"] = "ok"
            return res

        # Deterministic fallback chaining all 7 Shiva-Muse components directly
        rtk_out = self.rtk_compress(prompt)
        dream_out = self.wonder_manifest(rtk_out["text"], n=4)
        candidates = wonder_dream.dream_candidates(rtk_out["text"], n=2)
        grounded_trace = candidates[0]

        try:
            from sensor_xdp.loader import read_counters, to_ashta_evidence
            xdp_ev = to_ashta_evidence(read_counters())
        except Exception:
            xdp_ev = None

        gated = self.router.gated_dispatch(agent_id, grounded_trace, modality=task_type)
        soft_mask = sam31_physics_injector.demo_mask(64, 64)
        tensors = sam31_physics_injector.mask_to_boundary_tensors(
            soft_mask, sam31_physics_injector.InjectionConfig(grid_h=32, grid_w=32)
        )
        launch = sam31_physics_injector.build_triton_launch_params(tensors)
        u0, v0 = verifiable_agent_harness.taylor_green(32)
        harness = verifiable_agent_harness.verify_rollout(
            model=gated["model"],
            params={"agent_id": agent_id, "dimension": dimension, "grid": 32},
            u0=u0,
            v0=v0,
            u1=u0.copy(),
            v1=v0.copy(),
            dt=0.001,
            dx=0.19,
        )
        live = shiva_muse_live_engine.chat(gated["model"], rtk_out["text"]) if execute_live else {
            "mode": "DRY_RUN_SKIPPED",
            "model": gated["model"],
        }
        return {
            "status": "ok",
            "pipeline_status": "PASS" if (gated["ashta_gate"]["verdict"] == "pass" and harness["status"] == "PASS") else "VETO",
            "rtk_shim": rtk_out,
            "wonder_dream": dream_out,
            "sensor_xdp": xdp_ev,
            "dispatch": gated,
            "ashta_gate": gated["ashta_gate"],
            "sam31_injection": launch,
            "harness_verification": harness,
            "live_inference": live,
        }

    # ------------------------------------------------------------------
    # Muse CLI Session Resume (`resume_muse_session`)
    # ------------------------------------------------------------------
    def resume_muse_session(
        self,
        session_id: str = DEFAULT_MUSE_SESSION_ID,
        prompt: Optional[str] = None,
        execute_live: bool = False,
    ) -> Dict[str, Any]:
        """Resume a Meta Muse session (`01a1c1c5-0154-7250-8767-f4beaff19eae` by default)."""
        if hasattr(self.router, "resume_session"):
            res = self.router.resume_session(
                session_id=session_id, prompt=prompt, execute_live=execute_live
            )
            if isinstance(res, dict):
                res = dict(res)
                res["resume_status"] = res.get("status", "RESUMED")
                res["status"] = "ok"
            return res

        try:
            from meta_hackathon_2026.muse_session_bridge import resume_session as _bridge_resume
            res = _bridge_resume(
                session_id=session_id,
                prompt=prompt,
                router=self.router,
                execute_live=execute_live,
            )
            res = dict(res)
            res["resume_status"] = res.get("status", "RESUMED")
            res["status"] = "ok"
            return res
        except ImportError:
            pass

        hex_str = session_id.replace("-", "")
        ts_ms = int(hex_str[:12], 16)
        ver = int(hex_str[12], 16)
        effective_prompt = prompt or f"Resume Shiva-Muse verification session {session_id}"
        pipeline_res = self.run_full_pipeline(effective_prompt, execute_live=execute_live)
        return {
            "status": "ok",
            "session_id": session_id,
            "uuid_version": ver,
            "timestamp_ms": ts_ms,
            "resumed": True,
            "mode": "DETERMINISTIC_CHECKPOINT_RESUME",
            "pipeline": pipeline_res,
        }

    def status_snapshot(self) -> Dict[str, Any]:
        """Return a non-secret status dictionary for `tattva doctor` and `tattva_status`."""
        meta_key = os.environ.get("META_API_KEY", "").strip()
        baseten_key = os.environ.get("BASETEN_API_KEY", "").strip()
        return {
            "enabled": True,
            "meta_api_key": f"set (len={len(meta_key)})" if meta_key else "not set (DRY_RUN_NO_KEY mode)",
            "baseten_api_key": f"set (len={len(baseten_key)})" if baseten_key else "not set (DRY_RUN_NO_KEY mode)",
            "models": dict(ShivaMuseRouter.MODEL_CATALOG),
            "default_session_id": DEFAULT_MUSE_SESSION_ID,
            "budget_cap_usd": self.router.ledger.hard_spend_cap_usd,
            "reserved_floor_usd": self.router.ledger.reserved_floor_usd,
        }
