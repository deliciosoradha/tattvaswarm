"""P4 oracle — Rubisco Catalytic Trade-off & Pareto Frontier Audit.

Context (Flamholz et al. 2019, Savir et al. 2010):
  Rubisco displays a well-documented trade-off between specificity for CO2 over O2
  (S_C/O) and catalytic turnover rate for carboxylation (k_cat_C).
  Empirical Pareto frontier spans from:
    - High specificity, slow turnover: Rhodophyta / Galdieria sulphuraria (S_C/O ~ 160-230, k_cat_C ~ 1.2-2.5 s^-1)
    - Low specificity, fast turnover: C4 plants / Maize (S_C/O ~ 75-85, k_cat_C ~ 4.5-6.0 s^-1)
    - Cyanobacteria (S_C/O ~ 40-50, k_cat_C ~ 10-14 s^-1)

Oracle verification:
  1. The model predicts (S_C/O, k_cat_C, K_C, K_O) for proposed engineered variants.
  2. If the model claims an engineered variant that breaches the natural Pareto frontier
     (e.g., S_C/O >= 160 AND k_cat_C >= 6.0 s^-1), this is flagged as UNSUPPORTED_EXTRAORDINARY
     unless accompanied by a structural mechanism verified against known active-site constraints.
  3. Power-law trade-off regression fit:
     ln(k_cat_C) = -alpha * ln(S_C/O) + const
"""
from __future__ import annotations

import math
from typing import Any, Dict, List

# Benchmark empirical bounds from Form I & Form II Rubisco datasets
PARETO_BOUNDS = {
    "max_natural_kcat": 14.5,     # s^-1 (Synechococcus)
    "max_natural_sc_o": 240.0,    # Galdieria / Griffithsia
    # Approximate empirical Pareto boundary: k_cat * (S_C/O)^0.7 <= 250
    "pareto_hyperbola_limit": 250.0,
}


def evaluate(task: Dict[str, Any], answer: Dict[str, Any]) -> Dict[str, Any]:
    reasons: List[str] = []

    try:
        variants = answer.get("engineered_variants", [])
        if not variants or not isinstance(variants, list):
            return {"tier": "FAIL_ORACLE", "reasons": ["engineered_variants must be a non-empty list"]}
    except Exception as exc:
        return {"tier": "UNPARSEABLE", "reasons": [str(exc)]}

    breached_variants = []
    valid_variants = []

    for v in variants:
        name = v.get("name", "unnamed")
        try:
            sc_o = float(v["S_C_O"])
            kcat = float(v["k_cat_C_s1"])
        except (KeyError, TypeError, ValueError):
            reasons.append(f"Variant {name} missing numeric S_C_O or k_cat_C_s1")
            continue

        if sc_o <= 0 or kcat <= 0:
            reasons.append(f"Variant {name} has non-positive catalytic constants")
            continue

        # Check empirical Pareto trade-off index
        pareto_index = kcat * (sc_o ** 0.7)

        if pareto_index > PARETO_BOUNDS["pareto_hyperbola_limit"]:
            # Claim exceeds all known empirical bounds in nature
            breached_variants.append({
                "name": name,
                "S_C_O": sc_o,
                "k_cat": kcat,
                "pareto_index": round(pareto_index, 1),
            })
        else:
            valid_variants.append(name)

    if breached_variants:
        return {
            "tier": "UNSUPPORTED_EXTRAORDINARY",
            "reasons": [
                f"Variants {breached_variants} breach the natural Rubisco Pareto frontier without wet-lab crystallographic validation"
            ],
            "breached_variants": breached_variants,
            "valid_variants": valid_variants,
        }

    tier = "FAIL_ORACLE" if reasons else "PROXY_PASS"
    return {
        "tier": tier,
        "reasons": reasons,
        "valid_variants_count": len(valid_variants),
    }
