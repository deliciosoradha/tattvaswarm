"""P2 oracle — 1D multi-layer transient Thermal Protection System (TPS).

Model proposes layer thicknesses for:
  Layer 1: UHTC (e.g. ZrB2-SiC or C/SiC) — surface exposed to aerothermal heat pulse
  Layer 2: Carbon-Carbon (C/C) or structural insulator
  Layer 3: Aerogel insulation (e.g. silica or carbon aerogel)
  Substrate: Titanium or Aluminum airframe structure

Physics:
  1D transient heat conduction: rho * cp * dT/dt = d/dx ( k * dT/dx )
  Surface boundary: -k * dT/dx = q_aero(t) - eps * sigma * (T_surf^4 - T_space^4)
  Backside boundary: adiabatic (conservative) or convective cooling
  Interface continuity: T_left = T_right, k_left * dT/dx = k_right * dT/dx

Oracle implementation:
  Implicit / semi-implicit finite difference (Crank-Nicolson) over non-uniform grid.
  Acceptance criteria:
    1. T_backside_max <= T_structural_limit (e.g. 450 K for Al, 700 K for Ti)
    2. T_surf_max <= T_ablation_limit for UHTC (e.g. 2500 K)
    3. Areal mass (sum of rho_i * L_i) is minimized and within realistic budget
"""
from __future__ import annotations

import math
from typing import Any, Dict, List
import numpy as np

SIGMA = 5.670374419e-8  # Stefan-Boltzmann constant (W/m^2/K^4)

# Reference material database at representative temperatures (density kg/m^3, cp J/kg/K, k W/m/K, max_T K)
MATERIALS = {
    "uhtc_zrb2_sic": {"rho": 5600.0, "cp": 700.0, "k": 35.0, "max_T": 2500.0},
    "c_c_composite": {"rho": 1750.0, "cp": 1200.0, "k": 15.0, "max_T": 2000.0},
    "silica_aerogel": {"rho": 150.0, "cp": 1000.0, "k": 0.03, "max_T": 1100.0},
    "titanium_grade5": {"rho": 4430.0, "cp": 526.0, "k": 6.7, "max_T": 700.0},
    "aluminum_2024": {"rho": 2780.0, "cp": 875.0, "k": 121.0, "max_T": 450.0},
}


def simulate_1d_tps(
    layers: List[Dict[str, Any]],
    q_peak: float = 7.5e5,    # 0.75 MW/m^2 representative moderate re-entry heat flux
    t_pulse: float = 200.0,   # seconds duration
    t_total: float = 600.0,   # seconds total monitoring (soak-through)
    t_initial: float = 300.0, # K initial temperature
    dt: float = 1.0,          # 1.0 s timestep
    cells_per_layer: int = 10,
) -> Dict[str, Any]:
    """Fast 1D finite-volume transient thermal solver with radiation boundary."""
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
    dx = np.array(dx_list)
    rho = np.array(rho_list)
    cp = np.array(cp_list)
    k = np.array(k_list)

    cap = rho * cp * dx  # Thermal capacitance per unit area (J/m^2/K)
    T = np.full(N, t_initial, dtype=np.float64)

    # Precalculate harmonic interface conductances G_i (W/m^2/K)
    G = np.zeros(N + 1)
    G[1:N] = 2.0 * k[:-1] * k[1:] / (k[:-1] * dx[1:] + k[1:] * dx[:-1])
    G[0] = 0.0
    G[N] = 0.0  # adiabatic back

    # Unconditionally stable Implicit Euler (backward Euler) with surface radiation linearization
    # For each time step, solve tridiagonal system:
    # A_i * T_{i-1}^{n+1} + B_i * T_i^{n+1} + C_i * T_{i+1}^{n+1} = D_i
    n_steps = int(t_total / dt)
    T_surf_max = t_initial
    T_back_max = t_initial

    eps = 0.85
    for s in range(n_steps):
        t_curr = s * dt
        # Heat pulse
        if t_curr <= t_pulse * 0.2:
            q_in = q_peak * (t_curr / (t_pulse * 0.2))
        elif t_curr <= t_pulse * 0.8:
            q_in = q_peak
        elif t_curr <= t_pulse:
            q_in = q_peak * (1.0 - (t_curr - t_pulse * 0.8) / (t_pulse * 0.2))
        else:
            q_in = 0.0

        # Newton / Picard iteration for radiation boundary: q_rad = eps * sigma * T_surf^4
        # Linearize: q_rad(T) ~= q_rad(T_old) + 4 * eps * sigma * T_old^3 * (T - T_old)
        T_old = T.copy()
        for _ in range(3):
            h_rad = 4.0 * eps * SIGMA * (T_old[0] ** 3)
            q_rad_const = eps * SIGMA * (T_old[0] ** 4) - h_rad * T_old[0]

            # Build tridiagonal matrix
            # Cell 0: cap[0]/dt * (T_0 - T_prev) = q_in - (h_rad * T_0 + q_rad_const) - G[1]*(T_0 - T_1)
            # Cell i: cap[i]/dt * (T_i - T_prev) = G[i]*(T_{i-1} - T_i) - G[i+1]*(T_i - T_{i+1})
            # Cell N-1: adiabatic back (G[N]=0)
            diag = cap / dt + G[:-1] + G[1:]
            diag[0] += h_rad
            lower = -G[1:N]
            upper = -G[1:N]
            rhs = (cap / dt) * T.copy()
            rhs[0] += (q_in - q_rad_const)

            # Thomas algorithm (tridiagonal matrix solve)
            c_prime = np.zeros(N - 1)
            d_prime = np.zeros(N)

            c_prime[0] = upper[0] / diag[0]
            d_prime[0] = rhs[0] / diag[0]

            for i in range(1, N - 1):
                m = 1.0 / (diag[i] - lower[i - 1] * c_prime[i - 1])
                c_prime[i] = upper[i] * m
                d_prime[i] = (rhs[i] - lower[i - 1] * d_prime[i - 1]) * m

            m_last = 1.0 / (diag[N - 1] - lower[N - 2] * c_prime[N - 2])
            d_prime[N - 1] = (rhs[N - 1] - lower[N - 2] * d_prime[N - 2]) * m_last

            T_new = np.zeros(N)
            T_new[N - 1] = d_prime[N - 1]
            for i in range(N - 2, -1, -1):
                T_new[i] = d_prime[i] - c_prime[i] * T_new[i + 1]

            T_old = np.clip(T_new, 100.0, 3500.0)

        T = T_old.copy()
        if T[0] > T_surf_max:
            T_surf_max = float(T[0])
        if T[-1] > T_back_max:
            T_back_max = float(T[-1])

    areal_mass = sum(float(lay["thickness_m"]) * MATERIALS[lay["material"]]["rho"] for lay in layers)

    return {
        "max_surface_T_K": round(float(T_surf_max), 1),
        "max_backside_T_K": round(float(T_back_max), 1),
        "final_backside_T_K": round(float(T[-1]), 1),
        "areal_mass_kg_m2": round(float(areal_mass), 2),
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
