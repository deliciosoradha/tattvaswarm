"""P2 oracle — 1D multi-layer transient Thermal Protection System (TPS).

Model proposes layer thicknesses for:
  Layer 1: UHTC (e.g. ZrB2-SiC or C/SiC) — surface exposed to aerothermal heat pulse
  Layer 2: Carbon-Carbon (C/C) or structural insulator
  Layer 3: Aerogel insulation (e.g. silica or carbon aerogel)
  Substrate: Titanium or Aluminum airframe structure

Governing Equations:
  1D transient heat conduction: rho * cp * dT/dt = d/dx ( k * dT/dx )
  Surface boundary: -k * dT/dx = q_aero(t) - eps * sigma * (T_surf^4 - T_space^4)
  Backside boundary: adiabatic (conservative)
  Interface continuity: T_left = T_right, k_left * dT/dx = k_right * dT/dx

Numerical Method:
  Unconditionally stable Implicit Euler (backward Euler) finite volume method with
  Thomas algorithm (tridiagonal solver) and Newton/Picard linearization of radiative surface loss.
  Temperature profiles are checked for numerical convergence and physical feasibility.
  Divergence is explicitly reported, never silently hidden.

Acceptance criteria:
  1. T_backside_max <= T_structural_limit (e.g. 450 K for Al bondline, 700 K for Ti)
  2. T_surf_max <= T_ablation_limit for UHTC (e.g. 2500 K)
  3. Areal mass (sum of rho_i * L_i) <= max_areal_mass_kg_m2
"""
from __future__ import annotations

import math
from typing import Any, Dict, List
import numpy as np

SIGMA = 5.670374419e-8  # Stefan-Boltzmann constant (W/m^2/K^4)

# Material thermophysical database (density kg/m^3, cp J/kg/K, k W/m/K, max_T K)
# References:
#   uhtc_zrb2_sic: Fahrenholtz et al. (2007) J. Am. Ceram. Soc. 90(5):1347-1364; Gasch et al. NASA TM-2004-212852
#   c_c_composite: Savage, Carbon-Carbon Composites, Chapman & Hall (1993)
#   silica_aerogel: NASA Glenn Aerogel Insulation; Fricke & Tillotson (1997) Thin Solid Films 297:212-223
#   titanium_grade5: MMPDS-01, Ti-6Al-4V annealed
#   aluminum_2024: MMPDS-01, Al 2024-T3 (structural bondline limit 450 K)
MATERIALS = {
    "uhtc_zrb2_sic": {"rho": 5600.0, "cp": 700.0, "k": 35.0, "max_T": 2500.0},
    "c_c_composite": {"rho": 1750.0, "cp": 1200.0, "k": 15.0, "max_T": 2000.0},
    "silica_aerogel": {"rho": 150.0, "cp": 1000.0, "k": 0.03, "max_T": 1100.0},
    "titanium_grade5": {"rho": 4430.0, "cp": 526.0, "k": 6.7, "max_T": 700.0},
    "aluminum_2024": {"rho": 2780.0, "cp": 875.0, "k": 121.0, "max_T": 450.0},
}


def simulate_1d_tps(
    layers: List[Dict[str, Any]],
    q_peak: float = 7.5e5,    # 0.75 MW/m^2 (representative lifting reentry trajectory, e.g. Space Shuttle / X-37B wing)
    t_pulse: float = 200.0,   # seconds duration of entry pulse
    t_total: float = 600.0,   # seconds total thermal soak-through monitoring
    t_initial: float = 300.0, # K initial structure temperature
    dt: float = 1.0,          # seconds timestep
    cells_per_layer: int = 10,
    eps: float = 0.85,
) -> Dict[str, Any]:
    """1D finite-volume transient thermal solver with radiation boundary and Thomas algorithm."""
    dx_list = []
    rho_list = []
    cp_list = []
    k_list = []

    for lay in layers:
        mat = MATERIALS[lay["material"]]
        thick = float(lay["thickness_m"])
        dx = thick / cells_per_layer
        for _ in range(cells_per_layer):
            dx_list.append(dx)
            rho_list.append(mat["rho"])
            cp_list.append(mat["cp"])
            k_list.append(mat["k"])

    N = len(dx_list)
    dx = np.array(dx_list, dtype=np.float64)
    rho = np.array(rho_list, dtype=np.float64)
    cp = np.array(cp_list, dtype=np.float64)
    k = np.array(k_list, dtype=np.float64)

    cap = rho * cp * dx  # Thermal capacitance per unit area (J/m^2/K)
    T = np.full(N, t_initial, dtype=np.float64)

    # Harmonic mean interface conductances G_i (W/m^2/K)
    G = np.zeros(N + 1, dtype=np.float64)
    G[1:N] = 2.0 * k[:-1] * k[1:] / (k[:-1] * dx[1:] + k[1:] * dx[:-1])
    G[0] = 0.0
    G[N] = 0.0  # adiabatic backside

    n_steps = max(int(t_total / dt), 1)
    T_surf_max = t_initial
    T_back_max = t_initial

    for s in range(n_steps):
        t_curr = s * dt
        # Trapezoidal heat pulse
        if t_curr <= t_pulse * 0.2:
            q_in = q_peak * (t_curr / max(t_pulse * 0.2, 1e-6))
        elif t_curr <= t_pulse * 0.8:
            q_in = q_peak
        elif t_curr <= t_pulse:
            q_in = q_peak * (1.0 - (t_curr - t_pulse * 0.8) / max(t_pulse * 0.2, 1e-6))
        else:
            q_in = 0.0

        # Picard/Newton iteration for radiation linearization: q_rad = eps * sigma * (T_surf^4 - 0)
        T_old = T.copy()
        for _ in range(3):
            T_surf_est = max(T_old[0], 50.0)
            h_rad = 4.0 * eps * SIGMA * (T_surf_est ** 3)
            q_rad_const = eps * SIGMA * (T_surf_est ** 4) - h_rad * T_surf_est

            diag = cap / dt + G[:-1] + G[1:]
            diag[0] += h_rad
            lower = -G[1:N]
            upper = -G[1:N]
            rhs = (cap / dt) * T.copy()
            rhs[0] += (q_in - q_rad_const)

            # Thomas algorithm (tridiagonal matrix solve)
            c_prime = np.zeros(N - 1, dtype=np.float64)
            d_prime = np.zeros(N, dtype=np.float64)

            c_prime[0] = upper[0] / diag[0]
            d_prime[0] = rhs[0] / diag[0]

            for i in range(1, N - 1):
                denom = diag[i] - lower[i - 1] * c_prime[i - 1]
                if abs(denom) < 1e-12:
                    return {"diverged": True, "reason": "Singular matrix in thermal solve"}
                c_prime[i] = upper[i] / denom
                d_prime[i] = (rhs[i] - lower[i - 1] * d_prime[i - 1]) / denom

            denom_last = diag[N - 1] - lower[N - 2] * c_prime[N - 2]
            if abs(denom_last) < 1e-12:
                return {"diverged": True, "reason": "Singular matrix at backside"}
            d_prime[N - 1] = (rhs[N - 1] - lower[N - 2] * d_prime[N - 2]) / denom_last

            T_new = np.zeros(N, dtype=np.float64)
            T_new[N - 1] = d_prime[N - 1]
            for i in range(N - 2, -1, -1):
                T_new[i] = d_prime[i] - c_prime[i] * T_new[i + 1]

            # Check for non-finite values
            if not np.all(np.isfinite(T_new)):
                return {"diverged": True, "reason": "Non-finite temperatures produced"}

            T_old = T_new.copy()

        # Check for unphysical divergence
        if np.any(T_old < 50.0) or np.any(T_old > 4500.0):
            return {
                "diverged": True,
                "reason": f"Temperature out of physical range [50, 4500 K]: min={T_old.min():.1f}, max={T_old.max():.1f}",
            }

        T = T_old.copy()
        if T[0] > T_surf_max:
            T_surf_max = float(T[0])
        if T[-1] > T_back_max:
            T_back_max = float(T[-1])

    areal_mass = sum(float(lay["thickness_m"]) * MATERIALS[lay["material"]]["rho"] for lay in layers)

    return {
        "diverged": False,
        "max_surface_T_K": round(float(T_surf_max), 1),
        "max_backside_T_K": round(float(T_back_max), 1),
        "final_backside_T_K": round(float(T[-1]), 1),
        "areal_mass_kg_m2": round(float(areal_mass), 2),
    }


def simulate_analytic_slab_verification(
    q_const: float = 5.0e4,   # 50 kW/m^2 constant flux
    t_duration: float = 30.0, # 30 seconds
    thickness_m: float = 0.20,# Thick enough to act as semi-infinite
    t_initial: float = 300.0,
) -> Dict[str, float]:
    """Verifies solver against closed-form semi-infinite solid surface temperature:
    T_surf(t) = T_0 + (2 * q_0 / sqrt(pi * k * rho * cp)) * sqrt(t)
    Radiation is turned off (eps=0).
    """
    mat = MATERIALS["c_c_composite"]
    res = simulate_1d_tps(
        layers=[{"material": "c_c_composite", "thickness_m": thickness_m}],
        q_peak=q_const,
        t_pulse=t_duration,
        t_total=t_duration,
        t_initial=t_initial,
        dt=0.2,
        cells_per_layer=50,
        eps=0.0, # No radiation for pure conduction test
    )
    if res.get("diverged"):
        return {"error": res.get("reason", "diverged")}

    k, rho, cp = mat["k"], mat["rho"], mat["cp"]
    analytic_delta_t = (2.0 * q_const / math.sqrt(math.pi * k * rho * cp)) * math.sqrt(t_duration)
    analytic_surf_T = t_initial + analytic_delta_t

    # Half-cell extrapolation from cell centroid to boundary surface: T_surf = T_cell0 + q * (dx/2) / k
    dx = thickness_m / 50.0
    sim_surf_T = res["max_surface_T_K"] + q_const * (dx / 2.0) / k
    rel_error = abs(sim_surf_T - analytic_surf_T) / analytic_surf_T

    return {
        "analytic_surf_T_K": round(analytic_surf_T, 2),
        "numerical_surf_T_K": round(sim_surf_T, 2),
        "relative_error": round(rel_error, 4),
    }


def evaluate(task: Dict[str, Any], answer: Dict[str, Any]) -> Dict[str, Any]:
    limits = task.get("limits", {
        "max_surface_T_K": 2500.0,
        "max_backside_T_K": 450.0,  # e.g. aluminum bondline limit
        "max_areal_mass_kg_m2": 45.0,
    })
    reasons = []

    try:
        layers = answer["layers"]
        if not isinstance(layers, list) or len(layers) < 2:
            return {"tier": "FAIL_ORACLE", "reasons": ["layers must be a list of at least 2 layers"]}
        for lay in layers:
            mat = lay.get("material")
            thick = float(lay.get("thickness_m", 0.0))
            if mat not in MATERIALS:
                return {"tier": "FAIL_ORACLE", "reasons": [f"Unknown material: {mat}"]}
            if thick <= 0.0 or thick > 0.2:
                return {"tier": "FAIL_ORACLE", "reasons": [f"Unrealistic layer thickness: {thick} m"]}
    except (KeyError, TypeError, ValueError) as exc:
        return {"tier": "UNPARSEABLE", "reasons": [f"Invalid layers specification: {exc}"]}

    res = simulate_1d_tps(layers)

    if res.get("diverged"):
        return {
            "tier": "FAIL_ORACLE",
            "reasons": [f"Simulation diverged: {res.get('reason')}"],
            "simulation": res,
        }

    if res["max_surface_T_K"] > limits["max_surface_T_K"]:
        reasons.append(f"Surface T {res['max_surface_T_K']:.1f} K exceeds limit {limits['max_surface_T_K']} K")
    if res["max_backside_T_K"] > limits["max_backside_T_K"]:
        reasons.append(f"Backside soak T {res['max_backside_T_K']:.1f} K exceeds bondline limit {limits['max_backside_T_K']} K")
    if res["areal_mass_kg_m2"] > limits["max_areal_mass_kg_m2"]:
        reasons.append(f"Areal mass {res['areal_mass_kg_m2']:.1f} kg/m^2 exceeds limit {limits['max_areal_mass_kg_m2']} kg/m^2")

    tier = "FAIL_ORACLE" if reasons else "PROXY_PASS"
    return {
        "tier": tier,
        "reasons": reasons,
        "simulation": res,
    }
