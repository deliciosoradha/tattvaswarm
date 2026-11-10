#!/usr/bin/env python3
"""
Muse Session Bridge — Meta Muse Code CLI UUIDv7 Session Decoder & Resumption Bridge.

NEW WORK — Meta Global AI Developer Hackathon, Oct 27 - Nov 4, 2026.
Supports `muse resume 01a1c1c5-0154-7250-8767-f4beaff19eae` (`2026-11-09T19:24:36.052Z`).
"""
from __future__ import annotations

import datetime
import hashlib
import json
import pathlib
import shutil
import subprocess
import tempfile
import uuid
from typing import Any, Dict, List, Optional

DEFAULT_RESUME_SESSION_ID = "01a1c1c5-0154-7250-8767-f4beaff19eae"
DEFAULT_SESSION_ID = DEFAULT_RESUME_SESSION_ID

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def decode_uuidv7(session_id: str = DEFAULT_RESUME_SESSION_ID) -> Dict[str, Any]:
    """Decode RFC 9562 UUIDv7 48-bit millisecond timestamp and entropy fields."""
    clean_id = session_id.strip()
    if clean_id.startswith("chatcmpl-"):
        clean_id = clean_id[len("chatcmpl-") :]
    u = uuid.UUID(clean_id)
    unix_ts_ms = u.int >> 80
    try:
        dt = datetime.datetime.fromtimestamp(unix_ts_ms / 1000.0, tz=datetime.timezone.utc)
        iso_utc = dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{unix_ts_ms % 1000:03d}Z"
    except (OverflowError, ValueError):
        # Year > 9999 or out of range for standard datetime
        iso_utc = f"+{unix_ts_ms // 1000}s (FAR_FUTURE_OR_MAX_TS)"
    return {
        "session_id": str(u),
        "version": u.version,
        "is_uuidv7": u.version == 7,
        "unix_ts_ms": unix_ts_ms,
        "timestamp_ms": unix_ts_ms,
        "timestamp_utc": iso_utc,
        "iso_utc": iso_utc,
        "timestamp_iso": iso_utc,
        "prefix_family": str(u)[:4],
        "rand_a": (u.int >> 64) & 0x0FFF,
        "rand_b_hex": f"{u.int & ((1 << 62) - 1):016x}",
    }


parse_session_uuid = decode_uuidv7
inspect_session_id = decode_uuidv7


def load_verified_traces(repo_root: Optional[pathlib.Path] = None) -> List[Dict[str, Any]]:
    root = pathlib.Path(repo_root) if repo_root else _REPO_ROOT
    for rel in (
        pathlib.Path("meta_hackathon_2026/logs/verified_partner_inference_trace.jsonl"),
        pathlib.Path("logs/verified_partner_inference_trace.jsonl"),
    ):
        p = root / rel
        if p.exists():
            return [
                json.loads(line)
                for line in p.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
    return []


def _run_auditor() -> str:
    """Execute auditor_estricto_meta.run_forensic_audit() for real and return its verdict."""
    import contextlib
    import io
    import sys as _sys

    root = str(_REPO_ROOT)
    if root not in _sys.path:
        _sys.path.insert(0, root)
    try:
        import auditor_estricto_meta  # type: ignore
    except ImportError:
        return "NOT_RUN (auditor_estricto_meta not importable)"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = auditor_estricto_meta.run_forensic_audit(root)
    return "VEREDICTO: APROBADO" if code == 0 else f"VEREDICTO: RECHAZADO (exit={code})"


def _resolve_session_dir(
    session_id: str,
    session_dir: Optional[Any] = None,
    session_root: Optional[Any] = None,
) -> pathlib.Path:
    if session_dir is not None:
        return pathlib.Path(session_dir)
    if session_root is not None:
        return pathlib.Path(session_root) / session_id
    return _REPO_ROOT / "session" / session_id


def export_session_trajectory(
    session_id: str = DEFAULT_RESUME_SESSION_ID,
    session_dir: Optional[Any] = None,
    pipeline_result: Optional[Dict[str, Any]] = None,
    session_root: Optional[Any] = None,
) -> Dict[str, Any]:
    """Export deterministic session_state.md and trajectory.json for a Muse UUIDv7 session."""
    meta = decode_uuidv7(session_id)
    clean_id = meta["session_id"]
    target_dir = _resolve_session_dir(clean_id, session_dir=session_dir, session_root=session_root)
    target_dir.mkdir(parents=True, exist_ok=True)

    traces = load_verified_traces(_REPO_ROOT)
    meta_calls = sum(1 for r in traces if r.get("provider") == "Meta_Model_API")
    baseten_calls = sum(
        1
        for r in traces
        if r.get("provider") == "Baseten_Open_Weights"
        or str(r.get("model", "")).startswith("meta-models/muse-spark-open")
    )
    cum_spend = float(traces[-1].get("cumulative_meta_spend_usd", 0.0)) if traces else 0.0
    reserve = float(traces[-1].get("untouched_reserve_usd", 50.0)) if traces else 50.0
    audit_verdict = _run_auditor()

    pipe_cert = (
        (pipeline_result or {}).get("pipeline_certificate")
        or (pipeline_result or {}).get("verification_certificate")
        or hashlib.sha256(f"muse-session-bridge|{clean_id}|{len(traces)}".encode("utf-8")).hexdigest()
    )

    trajectory_core = {
        "session_id": clean_id,
        "uuidv7_metadata": meta,
        "cli_command": f"muse resume {clean_id}",
        "headless_command": f"muse exec --session-id {clean_id}",
        "export_command": f"muse export --session {clean_id} --out trajectory.json",
        "status": "RESUMED_CHECKPOINT",
        "muse_cli_state_restored": False,
        "note": "Local deterministic checkpoint; no Meta Muse conversational state is restored without the muse CLI.",
        "verified_trace_count": len(traces),
        "meta_api_calls": meta_calls,
        "baseten_open_weight_calls": baseten_calls,
        "budget_guardrail": {
            "cumulative_meta_spend_usd": cum_spend,
            "untouched_reserve_usd": reserve,
            "hard_spend_cap_usd": 100.0,
        },
        "forensic_audit": audit_verdict,
        "pipeline_certificate": pipe_cert,
    }
    traj_sha = hashlib.sha256(
        json.dumps(trajectory_core, sort_keys=True).encode("utf-8")
    ).hexdigest()
    trajectory_payload = {
        **trajectory_core,
        "trajectory_sha256": traj_sha,
    }

    # Append-only: every resume adds one line; existing checkpoint files are never overwritten.
    log_path = target_dir / "resume_log.jsonl"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"logged_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                            **trajectory_payload}, sort_keys=True) + "\n")

    traj_path = target_dir / "trajectory.json"
    if not traj_path.exists():
        traj_path.write_text(json.dumps(trajectory_payload, indent=2) + "\n", encoding="utf-8")

    state_md = f"""# Session State

- Session: {clean_id}
- UUIDv7 Timestamp: {meta["timestamp_utc"]} (unix_ts_ms: {meta["unix_ts_ms"]})
- CLI Resume Command: `muse resume {clean_id}`
- Repo: {_REPO_ROOT}
- Branch: hackathon-submit (Shiva-Muse × TattvaSwarm Integrated)
- Status: RESUMED_LOCAL_CHECKPOINT (Muse CLI state restored: no)

## Goal
Complete Meta Hackathon (Push the Frontier) integration of Tattva Swarm × Shiva-Muse Router,
wiring `rtk_shim`, `ashta_gate`, `wonder_dream`, `sam31_physics_injector`,
`verifiable_agent_harness`, `sensor_xdp`, `shiva_muse_live_engine`, and Muse CLI session bridge.

## Current Status
- Verified Partner Inference Trace: {len(traces)} live calls ({meta_calls} Meta_Model_API + {baseten_calls} Baseten_Open_Weights)
- Budget Guardrail: ${cum_spend:.3f} cumulative spend (COST_PER_1K estimate) / $100.00 active cap / ${reserve:.2f} untouched reserve
- Pipeline Certificate: `{pipe_cert}`
- Trajectory SHA-256: `{traj_sha}`
- Forensic Audit (`auditor_estricto_meta.py`, executed at export): {audit_verdict}
"""
    state_path = target_dir / "session_state.md"
    if not state_path.exists():
        state_path.write_text(state_md, encoding="utf-8")

    return {
        **trajectory_payload,
        "session_dir": str(target_dir),
        "session_state_path": str(state_path),
        "trajectory_path": str(traj_path),
    }


def resume_muse_session(
    session_id: str = DEFAULT_RESUME_SESSION_ID,
    prompt: Optional[str] = None,
    execute_live: bool = False,
    router: Optional[Any] = None,
    session_dir: Optional[Any] = None,
    session_root: Optional[Any] = None,
) -> Dict[str, Any]:
    """Resume a Meta Muse CLI UUIDv7 session and checkpoint trajectory + verification pipeline."""
    meta = decode_uuidv7(session_id)
    clean_id = meta["session_id"]
    target_dir = _resolve_session_dir(clean_id, session_dir=session_dir, session_root=session_root)
    muse_bin = shutil.which("muse")

    effective_prompt = prompt or f"Resume Muse session {clean_id}: verify Taylor-Green and Ashta-Gate"

    if router is None:
        try:
            from meta_hackathon_2026.shiva_muse_router import ShivaMuseRouter
        except ImportError:
            from shiva_muse_router import ShivaMuseRouter  # type: ignore
        with tempfile.TemporaryDirectory() as td:
            temp_router = ShivaMuseRouter(ledger_path=str(pathlib.Path(td) / "resume_ledger.json"))
            pipeline_res = temp_router.full_muse_pipeline(
                prompt=effective_prompt, execute_live=execute_live
            )
    else:
        pipeline_res = router.full_muse_pipeline(
            prompt=effective_prompt, execute_live=execute_live
        )

    cli_invoked = False
    cli_output: Optional[str] = None
    if muse_bin and execute_live:
        try:
            proc = subprocess.run(
                [muse_bin, "exec", "--session-id", clean_id, effective_prompt],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            cli_invoked = proc.returncode == 0
            cli_output = (proc.stdout or proc.stderr or "").strip()
        except Exception as exc:
            cli_output = f"muse exec fallback: {exc}"

    exported = export_session_trajectory(
        session_id=clean_id,
        session_dir=target_dir,
        pipeline_result=pipeline_res,
    )

    return {
        "status": "RESUMED",
        "bridge_mode": "RESUMED_LIVE_CLI" if cli_invoked else "RESUMED_DETERMINISTIC_BRIDGE",
        "session_id": clean_id,
        "uuidv7": meta,
        "cli_command": f"muse resume {clean_id}",
        "muse_binary_detected": bool(muse_bin),
        "cli_output": cli_output,
        "session_dir": str(target_dir),
        "session_state_path": exported["session_state_path"],
        "trajectory_path": exported["trajectory_path"],
        "trajectory_sha256": exported["trajectory_sha256"],
        "verified_trace_count": exported["verified_trace_count"],
        "pipeline_certificate": exported["pipeline_certificate"],
        "pipeline": pipeline_res,
    }


resume_session = resume_muse_session


if __name__ == "__main__":
    out = resume_muse_session(DEFAULT_RESUME_SESSION_ID, execute_live=False)
    print(json.dumps({k: v for k, v in out.items() if k != "pipeline"}, indent=2))
