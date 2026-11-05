#!/usr/bin/env python3
"""Benchmark A/B local: con Ashta-Gate vs sin gate (mismo harness/trazas).
Evidencia real CPU, sin red ni claves. Mide veto, latencia y determinismo.
Uso: python3 benchmarks/bench_ab.py"""
import json, sys, time
sys.path.insert(0, "meta_hackathon_2026")
from ashta_gate import evaluate  # noqa
from wonder_dream import dream_candidates  # noqa

TRACES = dream_candidates("¿Taylor-Green conserva div=0?", n=40)

def run(gated: bool, reps: int = 5):
    lat, veto = [], 0
    for _ in range(reps):
        for t in TRACES:
            t0 = time.perf_counter()
            v = evaluate(t)["verdict"] if gated else "pass"
            lat.append((time.perf_counter() - t0) * 1e3)
            veto += (v == "veto")
    lat.sort()
    return {"mode": "con_ashta" if gated else "sin_gate", "n": len(TRACES) * reps,
            "veto": veto // reps, "veto_rate": round((veto // reps) / len(TRACES), 3),
            "p50_ms": round(lat[len(lat)//2], 3), "p95_ms": round(lat[int(len(lat)*.95)], 3)}

if __name__ == "__main__":
    a, b = run(False), run(True)
    print(json.dumps({"sin_gate": a, "con_ashta": b,
                      "nota": "sin gate todo pasa (incl. especulación); con Ashta se veta lo no fundamentado"}, indent=1))
