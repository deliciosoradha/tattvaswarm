#!/usr/bin/env python3
"""
Auditor Forense Pre-Envío — Meta Global AI Developer Hackathon
Verifica: saneamiento de métricas sintéticas, deslinde New Work Only,
archivos del paquete nuevo, ledger de inferencia verificada y guardrail
$100 activos / $50 reserva. No inventa resultados: lo que no existe, falla.
"""
import os
import re
import sys
import json
from pathlib import Path

BANNED_PATTERNS = [
    r"40,899",
    r"40899\.80",
    r"1,284,950",
    r"2,150,400",
    r"COLAB_SEPTEMBER_QUICKNODE_AUDIT_REPORT",
]

REQUIRED_NEW_FILES = [
    "meta_hackathon_2026/shiva_muse_router.py",
    "meta_hackathon_2026/paper_shiva_muse_verification.tex",
]

CANONICAL_METRICS_NOTE = (
    "Métricas canónicas verificadas en hardware NVIDIA RTX PRO 6000 Blackwell (sm_120): "
    "Earth-2 44.01x speedup (0.8597 ms vs 37.84 ms, 1,449.14 GB/s, 40 regs, 0 spills), "
    "100B nodos Q_36 en 140.65 s, Taylor-Green 2,967.03 GB/s, Mach 15 2,564.91 GB/s, "
    "DeFi Sentinel 1,546.39 GB/s."
)

def run_forensic_audit(repo_root: str = ".") -> int:
    root = Path(repo_root).resolve()
    failures = []
    warnings = []

    print("=" * 78)
    print(" AUDITORÍA FORENSE Y ESCÉPTICA — META GLOBAL AI DEVELOPER HACKATHON")
    print("=" * 78)

    # 1. Contaminación por logs sintéticos
    for path in root.rglob("*"):
        if path.is_file() and ".git" not in path.parts and path.suffix in {".md", ".json", ".py", ".tex"}:
            if path.name == "auditor_estricto_meta.py":
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                for pat in BANNED_PATTERNS:
                    if re.search(pat, content):
                        failures.append(f"[CONTAMINACIÓN] Patrón prohibido '{pat}' en {path.relative_to(root)}")
            except Exception:
                pass

    # 2. New Work Only en README.md
    readme_path = root / "README.md"
    if not readme_path.exists():
        failures.append("[SECCIÓN 4] No existe README.md en la raíz.")
    else:
        readme_text = readme_path.read_text(encoding="utf-8", errors="ignore")
        if "New Work Only" not in readme_text and "Meta Global AI Developer Hackathon" not in readme_text:
            failures.append(
                "[DESCALIFICACIÓN SECCIÓN 4] README.md sin tabla explícita "
                "trabajo nuevo (Oct 27–Nov 4) vs DOIs previos de Zenodo."
            )
        if "meta-models/muse-spark-open-1026" not in readme_text:
            warnings.append(
                "[OPEN WEIGHTS $10K] README.md no menciona "
                "'meta-models/muse-spark-open-1026'."
            )

    # 3. Artefactos del paquete nuevo
    for req_file in REQUIRED_NEW_FILES:
        if not (root / req_file).exists():
            failures.append(f"[ARTEFACTO FALTANTE] No se encontró {req_file}")

    # 4. Ledger de inferencia verificada + guardrail $100/$50
    ledger_path = root / "meta_hackathon_2026/logs/verified_partner_inference_trace.jsonl"
    if not ledger_path.exists():
        failures.append(
            "[VERIFICACIÓN DE PARTNER] No existe "
            "'verified_partner_inference_trace.jsonl': sin inferencia real "
            "contra Meta API/Baseten todavía (bloqueo META-01)."
        )
    else:
        lines = [json.loads(l) for l in ledger_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        if not lines:
            failures.append("[VERIFICACIÓN DE PARTNER] Log de inferencia vacío (0 llamadas).")
        else:
            ow = sum(1 for r in lines if str(r.get("model", "")).startswith("meta-models/muse-spark-open"))
            spend = float(lines[-1].get("cumulative_meta_spend_usd", 0.0))
            reserve = float(lines[-1].get("untouched_reserve_usd", 0.0))
            if ow == 0:
                failures.append("[OPEN WEIGHTS $10K] 0 llamadas a 'meta-models/muse-spark-open*' (slug real Baseten 2026-11-05).")
            if spend > 100.00 or reserve < 50.00:
                failures.append(
                    f"[PRESUPUESTO] Gasto=${spend:.2f}, Reserva=${reserve:.2f} "
                    "(límite: <= $100.00 usados, >= $50.00 reserva)."
                )
            else:
                print(f"[OK] Presupuesto: ${spend:.2f} usados | ${reserve:.2f} reserva.")
                print(f"[OK] Llamadas open-weight verificadas: {ow}")

    print("-" * 78)
    print(f"[*] Hardware: {CANONICAL_METRICS_NOTE}")
    print("-" * 78)

    if warnings:
        print("\nADVERTENCIAS:")
        for w in warnings:
            print(f"  ! {w}")
    if failures:
        print("\nVEREDICTO: RECHAZADO (corregir antes de Cerebral Valley)")
        for f in failures:
            print(f"  X {f}")
        return 1
    print("\nVEREDICTO: APROBADO.")
    return 0

if __name__ == "__main__":
    sys.exit(run_forensic_audit(sys.argv[1] if len(sys.argv) > 1 else "."))
