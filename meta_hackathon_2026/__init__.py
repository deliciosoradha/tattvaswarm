"""Shiva-Muse Core Package — Meta Global AI Developer Hackathon Edition."""
from __future__ import annotations

from .shiva_muse_router import CreditLedger, ShivaMuseRouter
from .ashta_gate import AshtaThresholds, evaluate as ashta_evaluate, score_trace
from .wonder_dream import (
    dream_candidates,
    manifest,
    shiva_dance_resolve,
    dream_emulate_108m,
)
from .rtk_shim import redact, compress
from .sam31_physics_injector import (
    InjectionConfig,
    binarize_mask,
    resize_nearest,
    mask_to_boundary_tensors,
    build_triton_launch_params,
    save_injection_bundle,
    demo_mask,
)
from .verifiable_agent_harness import (
    InvariantThresholds,
    divergence_2d,
    max_divergence,
    energy_residual,
    cfl_number,
    certificate_hash,
    verify_rollout,
    taylor_green,
)
from .shiva_muse_live_engine import list_models, chat, chat_baseten
from .muse_session_bridge import (
    DEFAULT_RESUME_SESSION_ID,
    DEFAULT_SESSION_ID,
    decode_uuidv7,
    resume_muse_session,
    resume_session,
    export_session_trajectory,
)

__all__ = [
    "CreditLedger",
    "ShivaMuseRouter",
    "AshtaThresholds",
    "ashta_evaluate",
    "score_trace",
    "dream_candidates",
    "manifest",
    "shiva_dance_resolve",
    "dream_emulate_108m",
    "redact",
    "compress",
    "InjectionConfig",
    "binarize_mask",
    "resize_nearest",
    "mask_to_boundary_tensors",
    "build_triton_launch_params",
    "save_injection_bundle",
    "demo_mask",
    "InvariantThresholds",
    "divergence_2d",
    "max_divergence",
    "energy_residual",
    "cfl_number",
    "certificate_hash",
    "verify_rollout",
    "taylor_green",
    "list_models",
    "chat",
    "chat_baseten",
    "DEFAULT_RESUME_SESSION_ID",
    "DEFAULT_SESSION_ID",
    "decode_uuidv7",
    "resume_muse_session",
    "resume_session",
    "export_session_trajectory",
]
