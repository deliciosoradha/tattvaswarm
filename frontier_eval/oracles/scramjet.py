"""P1 oracle — quasi-1D scramjet cycle (ideal gas, gamma constant).

Chain: N oblique ramp shocks (weak branch) -> constant-area Rayleigh heat
addition -> isentropic expansion to freestream static pressure.
Every relation is a closed-form textbook equation (NACA Report 1135);
reference values are pinned in tests/test_frontier_oracles.py.

This is a *proxy*: it ignores friction, mixing losses, dissociation and
real-gas effects. Passing it means "physically self-consistent at the
cycle-analysis level", never "a working scramjet".
"""
from __future__ import annotations

import math
from typing import Any, Dict, List

GAMMA = 1.4
R_AIR = 287.05
CP = GAMMA * R_AIR / (GAMMA - 1.0)
H2_F_ST = 0.0292          # stoichiometric fuel/air mass ratio, hydrogen
H2_HPR = 120.0e6          # J/kg, lower heating value of H2


def _theta_from_beta(m: float, beta: float, g: float = GAMMA) -> float:
    num = 2.0 / math.tan(beta) * (m * m * math.sin(beta) ** 2 - 1.0)
    den = m * m * (g + math.cos(2.0 * beta)) + 2.0
    return math.atan(num / den)


def oblique_shock(m1: float, theta_deg: float, g: float = GAMMA) -> Dict[str, float]:
    """Weak-branch oblique shock. Raises ValueError if the shock detaches."""
    if m1 <= 1.0:
        raise ValueError(f"oblique shock needs supersonic flow (M={m1:.3f})")
    theta = math.radians(theta_deg)
    mu = math.asin(1.0 / m1)
    # locate beta_max (theta is unimodal in beta on (mu, pi/2))
    lo, hi = mu, math.pi / 2
    for _ in range(200):
        a = lo + (hi - lo) / 3
        b = hi - (hi - lo) / 3
        if _theta_from_beta(m1, a, g) < _theta_from_beta(m1, b, g):
            lo = a
        else:
            hi = b
    beta_max = 0.5 * (lo + hi)
    if theta > _theta_from_beta(m1, beta_max, g) + 1e-12:
        raise ValueError(f"shock detached: theta={theta_deg:.2f} deg exceeds theta_max at M={m1:.3f}")
    lo, hi = mu, beta_max
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if _theta_from_beta(m1, mid, g) < theta:
            lo = mid
        else:
            hi = mid
    beta = 0.5 * (lo + hi)
    mn1 = m1 * math.sin(beta)
    p_ratio = 1.0 + 2.0 * g / (g + 1.0) * (mn1 ** 2 - 1.0)
    t_ratio = p_ratio * (2.0 + (g - 1.0) * mn1 ** 2) / ((g + 1.0) * mn1 ** 2)
    mn2 = math.sqrt((1.0 + 0.5 * (g - 1.0) * mn1 ** 2) / (g * mn1 ** 2 - 0.5 * (g - 1.0)))
    m2 = mn2 / math.sin(beta - theta)
    return {"beta_deg": math.degrees(beta), "M2": m2, "p_ratio": p_ratio, "T_ratio": t_ratio}


def rayleigh_t0_ratio(m: float, g: float = GAMMA) -> float:
    """T0/T0* for Rayleigh flow."""
    return (g + 1.0) * m * m * (2.0 + (g - 1.0) * m * m) / (1.0 + g * m * m) ** 2


def rayleigh_p_ratio(m: float, g: float = GAMMA) -> float:
    return (g + 1.0) / (1.0 + g * m * m)


def rayleigh_t_ratio(m: float, g: float = GAMMA) -> float:
    return (g + 1.0) ** 2 * m * m / (1.0 + g * m * m) ** 2


def _rayleigh_supersonic_mach(t0_ratio: float, g: float = GAMMA) -> float:
    """Invert T0/T0* on the supersonic branch (monotone decreasing toward 1 as M grows)."""
    lo, hi = 1.0, 50.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if rayleigh_t0_ratio(mid, g) > t0_ratio:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def evaluate(task: Dict[str, Any], answer: Dict[str, Any]) -> Dict[str, Any]:
    fs = task["freestream"]
    lim = task["limits"]
    m0, t0s, p0s = float(fs["mach"]), float(fs["T_K"]), float(fs["p_Pa"])
    reasons: List[str] = []
    try:
        ramps = [float(a) for a in answer["ramp_angles_deg"]]
        phi = float(answer["phi"])
    except (KeyError, TypeError, ValueError) as exc:
        return {"tier": "UNPARSEABLE", "reasons": [f"missing/invalid field: {exc}"]}
    if not 1 <= len(ramps) <= 4 or any(a <= 0 for a in ramps):
        return {"tier": "FAIL_ORACLE", "reasons": ["need 1-4 positive ramp angles"]}
    if not 0.0 < phi <= 1.0:
        return {"tier": "FAIL_ORACLE", "reasons": [f"phi={phi} outside (0, 1]"]}

    m, t, p = m0, t0s, p0s
    stages = []
    try:
        for a in ramps:
            s = oblique_shock(m, a)
            m, t, p = s["M2"], t * s["T_ratio"], p * s["p_ratio"]
            stages.append({"theta_deg": a, **{k: round(v, 6) for k, v in s.items()}})
    except ValueError as exc:
        return {"tier": "FAIL_ORACLE", "reasons": [str(exc)], "stages": stages}

    if m < lim["min_combustor_mach"]:
        reasons.append(f"combustor entry M={m:.3f} < {lim['min_combustor_mach']} (not a scramjet)")

    t01 = t * (1.0 + 0.5 * (GAMMA - 1.0) * m * m)
    q = lim.get("burner_efficiency", 0.9) * phi * H2_F_ST * H2_HPR
    f = phi * H2_F_ST
    t02 = t01 + q / CP
    t0_star = t01 / rayleigh_t0_ratio(m)
    out: Dict[str, Any] = {"combustor_entry_M": round(m, 6), "T01_K": round(t01, 3),
                           "T02_K": round(t02, 3), "T0_star_K": round(t0_star, 3), "stages": stages}
    if t02 > t0_star:
        reasons.append(f"thermal choking: T02={t02:.1f} K > T0*={t0_star:.1f} K")
        out.update({"tier": "FAIL_ORACLE", "reasons": reasons})
        return out

    m2 = _rayleigh_supersonic_mach(t02 / t0_star)
    t2 = t * rayleigh_t_ratio(m2) / rayleigh_t_ratio(m)
    p2 = p * rayleigh_p_ratio(m2) / rayleigh_p_ratio(m)
    if t2 > lim["max_combustor_static_T_K"]:
        reasons.append(f"combustor static T={t2:.1f} K > material limit {lim['max_combustor_static_T_K']} K")

    p02 = p2 * (1.0 + 0.5 * (GAMMA - 1.0) * m2 * m2) ** (GAMMA / (GAMMA - 1.0))
    if p02 <= p0s:
        reasons.append("no expansion possible: p02 <= freestream static p")
        out.update({"tier": "FAIL_ORACLE", "reasons": reasons})
        return out
    me = math.sqrt(2.0 / (GAMMA - 1.0) * ((p02 / p0s) ** ((GAMMA - 1.0) / GAMMA) - 1.0))
    te = t02 / (1.0 + 0.5 * (GAMMA - 1.0) * me * me)
    ue = me * math.sqrt(GAMMA * R_AIR * te)
    u0 = m0 * math.sqrt(GAMMA * R_AIR * t0s)
    spec_thrust = (1.0 + f) * ue - u0  # N per (kg/s of air)
    isp = spec_thrust / (f * 9.80665)
    if spec_thrust <= 0:
        reasons.append(f"specific thrust {spec_thrust:.1f} N·s/kg <= 0")

    claimed = answer.get("claimed_specific_thrust_Ns_per_kg")
    if claimed is not None:
        try:
            rel = abs(float(claimed) - spec_thrust) / max(abs(spec_thrust), 1e-9)
            if rel > 0.05:
                reasons.append(f"claimed specific thrust {float(claimed):.1f} differs {rel:.1%} from oracle {spec_thrust:.1f}")
        except (TypeError, ValueError):
            reasons.append("claimed_specific_thrust not numeric")

    out.update({"combustor_exit_M": round(m2, 6), "combustor_static_T_K": round(t2, 3),
                "exit_M": round(me, 6), "specific_thrust_Ns_per_kg": round(spec_thrust, 3),
                "fuel_Isp_s": round(isp, 2), "f": round(f, 6)})
    out["tier"] = "FAIL_ORACLE" if reasons else "PROXY_PASS"
    out["reasons"] = reasons
    return out
