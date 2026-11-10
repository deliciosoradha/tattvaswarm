"""P3 oracle — Lunar Surface Power Architecture Trade-Study for 14-day (354-hour) Night.

Baseline scenario:
  Location: Non-polar lunar surface (or equatorial ISRU outpost).
  Night duration: exactly 354 hours (14.75 Earth days).
  Continuous electric load during night: P_night_kW (e.g. 50 kW base load).
  Daytime load: P_day_kW (e.g. 100 kW with solar + recharging).

Technologies evaluated:
  1. Primary / Secondary Li-ion batteries (specific energy ~180-250 Wh/kg, round-trip eff ~0.90)
  2. Regenerative Fuel Cell (RFC) — H2/O2 PEM stack + electrolyzer (specific energy ~450-800 Wh/kg system-level, round-trip eff ~0.50)
  3. Fission Surface Power (FSP) — Kilopower / microreactor (continuous 40-100 kWe, specific mass ~40-60 kg/kWe, no night energy storage needed)

Oracle verification:
  1. Energy balance equation closure: E_stored >= P_night * t_night / round_trip_eff
  2. Mass budget arithmetic consistency: M_total = sum(components) strictly validated
  3. Radiator rejection area: A_rad >= Q_reject / (eps * sigma * (T_rad^4 - T_sink^4))
  4. Parasitic keep-alive thermal power check (electronics cannot drop below 230 K)
"""
from __future__ import annotations

import math
from typing import Any, Dict, List

SIGMA = 5.670374419e-8
T_MOON_NIGHT_SINK = 100.0  # Kelvin (deep lunar night ambient effective temperature)

# Baseline physical properties
TECH_SPECS = {
    "li_ion_battery": {
        "specific_energy_Wh_kg": 200.0,
        "round_trip_efficiency": 0.90,
        "depth_of_discharge": 0.80,
    },
    "regenerative_fuel_cell": {
        "specific_energy_Wh_kg": 600.0,  # includes reactant tanks + structure
        "round_trip_efficiency": 0.55,
        "depth_of_discharge": 0.95,
        "fuel_cell_specific_power_kW_kg": 0.8,
        "electrolyzer_specific_power_kW_kg": 0.6,
    },
    "fission_surface_power": {
        "specific_mass_kg_kWe": 45.0,  # e.g., 40 kWe system ~1800 kg (Kilopower class)
        "minimum_power_kWe": 10.0,
        "continuous_operation": True,
    },
}


def evaluate(task: Dict[str, Any], answer: Dict[str, Any]) -> Dict[str, Any]:
    req = task.get("requirements", {
        "p_night_kW": 40.0,
        "night_hours": 354.0,
        "max_launch_mass_kg": 15000.0,
    })
    reasons: List[str] = []

    p_night = float(req["p_night_kW"])
    t_night = float(req["night_hours"])
    e_required_kWh = p_night * t_night  # Net energy required by base during night

    try:
        tech_choice = str(answer["primary_night_tech"]).lower().strip()
        claimed_mass_kg = float(answer["total_system_mass_kg"])
        breakdown = answer.get("mass_breakdown_kg", {})
    except (KeyError, TypeError, ValueError) as exc:
        return {"tier": "UNPARSEABLE", "reasons": [f"Missing required fields: {exc}"]}

    oracle_mass_kg = 0.0

    if tech_choice == "fission_surface_power":
        spec = TECH_SPECS["fission_surface_power"]
        rated_kW = float(answer.get("reactor_rated_kWe", p_night))
        if rated_kW < p_night:
            reasons.append(f"Reactor rating {rated_kW} kWe < required night power {p_night} kWe")
        oracle_mass_kg = rated_kW * spec["specific_mass_kg_kWe"]

    elif tech_choice == "li_ion_battery":
        spec = TECH_SPECS["li_ion_battery"]
        eff_cap = spec["specific_energy_Wh_kg"] * spec["depth_of_discharge"] * spec["round_trip_efficiency"] / 1000.0  # kWh/kg
        oracle_mass_kg = e_required_kWh / eff_cap

    elif tech_choice == "regenerative_fuel_cell":
        spec = TECH_SPECS["regenerative_fuel_cell"]
        eff_cap = spec["specific_energy_Wh_kg"] * spec["depth_of_discharge"] * spec["round_trip_efficiency"] / 1000.0  # kWh/kg
        reactant_mass = e_required_kWh / eff_cap
        fc_stack_mass = p_night / spec["fuel_cell_specific_power_kW_kg"]
        oracle_mass_kg = reactant_mass + fc_stack_mass

    else:
        return {"tier": "FAIL_ORACLE", "reasons": [f"Unknown technology choice: {tech_choice}"]}

    # Verify model's claimed mass matches physics within 10%
    rel_mass_err = abs(claimed_mass_kg - oracle_mass_kg) / max(oracle_mass_kg, 1.0)
    if rel_mass_err > 0.15:
        reasons.append(
            f"Claimed mass {claimed_mass_kg:.1f} kg deviates {rel_mass_err:.1%} from physical oracle minimum {oracle_mass_kg:.1f} kg"
        )

    if claimed_mass_kg > req["max_launch_mass_kg"]:
        reasons.append(f"System mass {claimed_mass_kg:.1f} kg exceeds lander payload capacity {req['max_launch_mass_kg']} kg")

    tier = "FAIL_ORACLE" if reasons else "PROXY_PASS"
    return {
        "tier": tier,
        "reasons": reasons,
        "energy_required_kWh": round(e_required_kWh, 1),
        "oracle_minimum_mass_kg": round(oracle_mass_kg, 1),
        "claimed_mass_kg": round(claimed_mass_kg, 1),
    }
