"""P4 oracle — Rubisco Catalytic Trade-off & Empirical Pareto Frontier Audit.

Reference:
  Flamholz, Noor, Bar-Even, Liebermeister & Milo (2019), "Revisiting trade-offs between
  Rubisco kinetic parameters", Biochemistry 58(47): 4663-4676.
  Dataset S2 (Merged Rubisco Kinetics, SHA-256: 98839cbc53dbb4cad9b2b20ebdeaab5f821f1075d21214e56c0054588d54d480).
  Savir et al. (2010), "The optimal enzyme for a given environment: the case of Rubisco",
  PNAS 107(8): 3475-3480.

Empirical Pareto Upper Envelope:
  The empirical trade-off between specificity (S_C/O) and carboxylation turnover (k_cat_C / vC)
  across Form I and Form II Rubiscos forms a strict Pareto front:
    - High specificity, slow turnover: Galdieria partita (S ~ 238, vC ~ 1.6 s^-1), Griffithsia monilis (S ~ 167, vC ~ 2.6 s^-1)
    - Moderate specificity, medium turnover: C4/C3 plants (Zea mays S ~ 78, vC ~ 4.4 s^-1; Poa palustris S ~ 112, vC ~ 4.2 s^-1)
    - Low specificity, high turnover: Cyanobacteria (Synechococcus S ~ 43-52, vC ~ 13.4-14.4 s^-1)

Oracle Verification:
  1. Input contains proposed engineered variants with S_C_O and k_cat_C_s1.
  2. Each variant is evaluated against the piecewise empirical Pareto upper boundary.
  3. A claim that exceeds the empirical frontier (+5% tolerance) without published crystallographic
     co-crystal validation is classified as UNSUPPORTED_EXTRAORDINARY.
  4. Physically plausible variants within natural bounds receive PROXY_PASS.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List

# Empirical Pareto non-dominated points from Flamholz et al. 2019 Dataset S2 (S_C/O, vC s^-1)
EMIRICAL_PARETO_POINTS = [
    (43.0, 14.40),   # Synechococcus elongatus PCC 7942
    (52.0, 13.40),   # Synechococcus 7002
    (55.0, 9.80),    # Cyanobium PCC7001
    (89.0, 7.10),    # Eragrostis tef
    (105.0, 5.80),   # Arctagrostis latifolia
    (106.0, 5.40),   # Puccinellia maritima
    (108.0, 5.10),   # Festuca gigantea
    (109.0, 4.40),   # Chenopodium murale
    (112.0, 4.20),   # Poa palustris
    (113.0, 3.40),   # Phaeodactylum tricornutum
    (116.0, 3.30),   # Phaeodactylum tricornutum (CS-29)
    (167.0, 2.60),   # Griffithsia monilis
    (238.0, 1.60),   # Galdieria partita Tokara
]


def max_empirical_kcat(sc_o: float) -> float:
    """Calculates the maximum turnover rate (s^-1) known across nature for a given specificity.
    Uses piecewise-linear interpolation across the empirical Pareto front from Flamholz 2019.
    """
    if sc_o <= EMIRICAL_PARETO_POINTS[0][0]:
        return EMIRICAL_PARETO_POINTS[0][1]
    if sc_o >= EMIRICAL_PARETO_POINTS[-1][0]:
        # Decay beyond highest known specificity (Galdieria 238)
        return EMIRICAL_PARETO_POINTS[-1][1] * (EMIRICAL_PARETO_POINTS[-1][0] / sc_o)

    for i in range(len(EMIRICAL_PARETO_POINTS) - 1):
        s0, v0 = EMIRICAL_PARETO_POINTS[i]
        s1, v1 = EMIRICAL_PARETO_POINTS[i + 1]
        if s0 <= sc_o <= s1:
            t = (sc_o - s0) / (s1 - s0)
            return v0 + t * (v1 - v0)
    return EMIRICAL_PARETO_POINTS[-1][1]


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

        max_allowed_kcat = max_empirical_kcat(sc_o)
        # 5% experimental error margin
        threshold = max_allowed_kcat * 1.05

        if kcat > threshold:
            breached_variants.append({
                "name": name,
                "S_C_O": sc_o,
                "k_cat": kcat,
                "max_natural_kcat": round(max_allowed_kcat, 2),
                "ratio_over_pareto": round(kcat / max_allowed_kcat, 2),
            })
        else:
            valid_variants.append(name)

    if breached_variants:
        return {
            "tier": "UNSUPPORTED_EXTRAORDINARY",
            "reasons": [
                f"Variant '{b['name']}' breaches natural Rubisco Pareto frontier (S={b['S_C_O']}, kcat={b['k_cat']} vs natural max {b['max_natural_kcat']} s^-1, ratio {b['ratio_over_pareto']}x) without crystallographic or wet-lab validation"
                for b in breached_variants
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
