#!/usr/bin/env python3
"""
Ashta-Gate — criterio de razonamiento para Tattva-Swarm (Shiva Router).

NEW WORK — Meta Global AI Developer Hackathon, Oct 27 - Nov 4, 2026.

En lugar de dejar que un agente "piense" en abierto y especule, cada
traza de razonamiento debe pasar una compuerta determinista de 8
aspectos (aṣṭadhā, Gita 7.4) antes de aceptarse:

  1 prithvi   fundamentacion  - cada afirmacion con evidencia citada
  2 jala      coherencia      - sin afirmaciones vacias ni duplicadas
  3 agni      falsabilidad    - prediccion comprobable / que la refutaria
  4 vayu      exploracion     - alternativas consideradas (>=2)
  5 akasha    alcance         - supuestos declarados
  6 manas     pertinencia     - responde la pregunta real (solape lexico)
  7 buddhi    inferencia      - incertidumbre cuantificada (+ invariantes)
  8 ahamkara  identidad       - limites declarados, sin autocontradiccion

Veredicto: veto si algun aspecto duro (prithvi, agni) es 0, o si la
media ponderada cae bajo el umbral. El veredicto se firma con el mismo
certificate_hash del harness verificable: criterio auditable, no opinion.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

from verifiable_agent_harness import certificate_hash

ASPECTS = ["prithvi", "jala", "agni", "vayu", "akasha", "manas", "buddhi", "ahamkara"]
HARD_ASPECTS = ("prithvi", "agni")
LIMIT_MARKERS = ("no se", "no sé", "unknown", "limit", "límite", "uncertain", "no puedo verificar")


@dataclass
class AshtaThresholds:
    mean_min: float = 0.55
    weights: Dict[str, float] = field(default_factory=lambda: {
        "prithvi": 2.0, "agni": 2.0, "buddhi": 1.5, "ahamkara": 1.5,
        "jala": 1.0, "vayu": 1.0, "akasha": 1.0, "manas": 1.0,
    })


def _tokens(text: str) -> set:
    return set(re.findall(r"[a-záéíóúñ0-9]+", (text or "").lower()))


def score_trace(trace: Dict[str, Any]) -> Dict[str, float]:
    claims = trace.get("claims", []) or []
    n = max(len(claims), 1)
    with_evidence = sum(1 for c in claims if str(c.get("evidence", "")).strip())
    prithvi = with_evidence / n if claims else 0.0

    texts = [str(c.get("text", "")).strip().lower() for c in claims]
    empty = sum(1 for t in texts if not t)
    dupes = len(texts) - len(set(texts))
    jala = max(0.0, 1.0 - (empty + dupes) / n) if claims else 0.0

    agni = 1.0 if str(trace.get("falsifiable_by", "")).strip() else 0.0

    alts = trace.get("alternatives", []) or []
    vayu = 1.0 if len(alts) >= 2 else (0.5 if len(alts) == 1 else 0.0)

    akasha = 1.0 if (trace.get("assumptions", []) or []) else 0.0

    q_tokens = _tokens(trace.get("question", ""))
    a_tokens = _tokens(trace.get("answer", ""))
    manas = (len(q_tokens & a_tokens) / len(q_tokens)) if q_tokens else 0.0

    unc = trace.get("uncertainty", None)
    buddhi = 0.6 if isinstance(unc, (int, float)) and 0.0 <= float(unc) <= 1.0 else 0.0
    inv = trace.get("invariants", {}) or {}
    if inv:
        ok = float(inv.get("cfl", 99)) <= 1.0 and float(inv.get("max_div", 99)) <= 1e-6
        buddhi = min(1.0, buddhi + (0.4 if ok else 0.0))

    blob = (trace.get("answer", "") + " " + " ".join(texts)).lower()
    declares_limits = any(m in blob for m in LIMIT_MARKERS) or bool(trace.get("limits"))
    ahamkara = 1.0 if declares_limits else 0.3

    return {
        "prithvi": round(prithvi, 4), "jala": round(jala, 4), "agni": agni,
        "vayu": vayu, "akasha": akasha, "manas": round(manas, 4),
        "buddhi": round(buddhi, 4), "ahamkara": ahamkara,
    }


def evaluate(trace: Dict[str, Any], thresholds: AshtaThresholds | None = None) -> Dict[str, Any]:
    th = thresholds or AshtaThresholds()
    scores = score_trace(trace)
    w = th.weights
    mean = sum(scores[a] * w[a] for a in ASPECTS) / sum(w.values())
    reasons: List[str] = [f"{a}=0 (aspecto duro)" for a in HARD_ASPECTS if scores[a] == 0.0]
    if mean < th.mean_min:
        reasons.append(f"media ponderada {mean:.3f} < umbral {th.mean_min}")
    verdict = "veto" if reasons else "pass"
    cert = certificate_hash("ashta-gate", {"scores": scores, "verdict": verdict},
                            {"mean": round(mean, 6)})
    return {
        "scores": scores,
        "weighted_mean": round(mean, 4),
        "verdict": verdict,
        "reasons": reasons,
        "certificate": cert,
        "input_sha256": hashlib.sha256(
            json.dumps(trace, sort_keys=True, default=str).encode("utf-8")).hexdigest(),
    }
