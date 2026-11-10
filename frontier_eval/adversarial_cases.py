"""Adversarial Cases & Deterministic Veto Pack.

Defines crafted adversarial candidate solutions across the 5 domains designed to test
oracle rejection capabilities. Every case in this pack MUST be rejected deterministically:
  - TPS: Thin aerogel layer leads to backside thermal soak > 450 K (bondline violation).
  - Rubisco: Claim breaches the empirical Flamholz 2019 Pareto frontier (S=170, kcat=5.0 s^-1).
  - Reverse Translatase: Frameshift / internal premature stop codon / non-canonical length.
  - Scramjet: Excessive equivalence ratio phi causing thermal choking (T02 > T0*).
  - Lunar Power: Underestimated mass claim violating energy balance closure.
"""
from __future__ import annotations

import pathlib
from typing import Any, Dict, List, Optional

from frontier_eval.oracles import scramjet, tps, lunar_power, rubisco, backtranslate

# Exact signatures matching evaluate(task, answer)
ADVERSARIAL_CASES: Dict[str, Dict[str, Any]] = {
    "scramjet": {
        "task": {
            "freestream": {"mach": 4.0, "T_K": 220.0, "p_Pa": 2000.0},
            "limits": {"min_combustor_mach": 1.2, "max_combustor_static_T_K": 2800.0, "burner_efficiency": 0.9},
        },
        "answer": {
            "ramp_angles_deg": [15.0, 15.0],
            "phi": 1.0,
        },
        "expected_tier": "FAIL_ORACLE",
        "expected_reason_substr": "thermal choking",
        "violation_description": "Excessive fuel equivalence ratio (phi=1.0) creates combustor thermal choking",
    },
    "tps": {
        "task": {
            "limits": {"max_surface_T_K": 2500.0, "max_backside_T_K": 450.0, "max_areal_mass_kg_m2": 45.0}
        },
        "answer": {
            "layers": [
                {"material": "uhtc_zrb2_sic", "thickness_m": 0.001},
                {"material": "silica_aerogel", "thickness_m": 0.002},
            ]
        },
        "expected_tier": "FAIL_ORACLE",
        "expected_reason_substr": "exceeds bondline limit",
        "violation_description": "Insufficient aerogel insulation (2mm) allows backside heat soak through > 450 K",
    },
    "rubisco": {
        "task": {},
        "answer": {
            "engineered_variants": [
                {"name": "Impossible_Miracle_Rubisco", "S_C_O": 170.0, "k_cat_C_s1": 5.0}
            ]
        },
        "expected_tier": "UNSUPPORTED_EXTRAORDINARY",
        "expected_reason_substr": "breaches natural Rubisco Pareto frontier",
        "violation_description": "Claim exceeds natural Flamholz 2019 Pareto envelope without crystallographic proof",
    },
    "backtranslate": {
        "task": {"target_peptide": "MKWVT", "gc_min_pct": 35.0, "gc_max_pct": 65.0},
        "answer": {
            "synthesized_dna": "ATGAAATGGGTGA",  # 13 bp, not multiple of 3
        },
        "expected_tier": "FAIL_ORACLE",
        "expected_reason_substr": "frameshift",
        "violation_description": "Non-triplet DNA sequence length causing frameshift error",
    },
    "lunar_power": {
        "task": {
            "requirements": {"p_night_kW": 40.0, "night_hours": 354.0, "max_launch_mass_kg": 25000.0}
        },
        "answer": {
            "primary_night_tech": "li_ion_battery",
            "total_system_mass_kg": 500.0,
        },
        "expected_tier": "FAIL_ORACLE",
        "expected_reason_substr": "deviates",
        "violation_description": "500 kg claimed mass deviates >95% from physical battery+solar storage requirement",
    },
}

ORACLE_MAP = {
    "scramjet": scramjet,
    "tps": tps,
    "rubisco": rubisco,
    "backtranslate": backtranslate,
    "lunar_power": lunar_power,
}


def run_adversarial(task_name: Optional[str] = None) -> Dict[str, Any]:
    """Executes deterministic veto checks on adversarial cases.

    Returns a structured verdict dictionary showing that all adversarial candidates
    are successfully caught and rejected.
    """
    targets = [task_name] if task_name else list(ADVERSARIAL_CASES.keys())
    results = {}
    passed_adversarial_count = 0  # Should remain 0!

    for name in targets:
        case = ADVERSARIAL_CASES[name]
        oracle = ORACLE_MAP[name]
        eval_result = oracle.evaluate(case["task"], case["answer"])

        tier = eval_result.get("tier")
        reasons = eval_result.get("reasons", [])
        reasons_text = " ".join(str(r) for r in reasons)

        tier_matches = (tier == case["expected_tier"])
        reason_matches = case["expected_reason_substr"].lower() in reasons_text.lower()
        veto_successful = tier in ("FAIL_ORACLE", "UNSUPPORTED_EXTRAORDINARY") and reason_matches

        if tier == "PROXY_PASS":
            passed_adversarial_count += 1

        results[name] = {
            "tier": tier,
            "expected_tier": case["expected_tier"],
            "veto_successful": veto_successful,
            "tier_matches": tier_matches,
            "reason_matches": reason_matches,
            "reasons": reasons,
            "violation": case["violation_description"],
        }

    all_vetoed = (passed_adversarial_count == 0) and all(r["veto_successful"] for r in results.values())
    return {
        "all_vetoed": all_vetoed,
        "cases_tested": len(targets),
        "false_passes": passed_adversarial_count,
        "results": results,
    }


def main():
    import sys
    task = sys.argv[1] if len(sys.argv) > 1 else None
    report = run_adversarial(task)
    print("=" * 60)
    print("ADVERSARIAL VETO PACK EXECUTION REPORT")
    print("=" * 60)
    print(f"Total Cases: {report['cases_tested']} | False Passes: {report['false_passes']}")
    print(f"Overall Veto Success: {'PASS (All Rejected)' if report['all_vetoed'] else 'FAIL (Leak Detected)'}")
    print("-" * 60)
    for name, r in report["results"].items():
        status = "REJECTED (OK)" if r["veto_successful"] else "LEAKED"
        print(f"[{status}] {name:15}: {r['tier']} -> {r['violation']}")
    if not report["all_vetoed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
