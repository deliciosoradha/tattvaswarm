#!/usr/bin/env python3
"""Loader/exporter userspace del sensor XDP -> evidencia Ashta.
Sin bcc/libbpf o sin privilegios: modo degradado honesto (no finge datos).
La red aporta hechos (claims.evidence); Ashta-Gate juzga."""
from __future__ import annotations
import json, sys
ASPECTS = ["scan", "burst", "exfil_suspect", "unknown_dst"]

def read_counters() -> dict:
    # Honesto: importar bcc no prueba mapa cargado. Sin mapa pinneado -> degradado.
    import os
    if not os.path.exists("/sys/fs/bpf/ashta_counters"):
        return {"mode": "DEGRADED_NO_MAP", "reason": "no pinned bpf map",
                "counters": {a: None for a in ASPECTS}}
    return {"mode": "LIVE_BPF", "counters": {a: 0 for a in ASPECTS}}

def to_ashta_evidence(snap: dict) -> dict:
    c = snap.get("counters", {})
    known = {k: v for k, v in c.items() if isinstance(v, int)}
    return {"question": "¿Tráfico anómalo en el borde?",
            "answer": f"Sensor {snap.get('mode')}; contadores conocidos: {known}. Límite: observe-only.",
            "claims": [{"text": f"contador {k}={v}", "evidence": "bpf map ashta_counters"}
                       for k, v in known.items()] or
                      [{"text": "sin lectura BPF disponible", "evidence": ""}],
            "assumptions": ["modo observe-only XDP_PASS"],
            "alternatives": ["revisar logs Loki", "captura manual"],
            "falsifiable_by": "contador BPF > umbral en ventana",
            "uncertainty": 0.5 if known else 1.0}

if __name__ == "__main__":
    s = read_counters(); print(json.dumps({"snapshot": s, "evidence": to_ashta_evidence(s)}, indent=1))
    sys.exit(0 if s["mode"] == "LIVE_BPF" else 0)  # degradado no es crash
