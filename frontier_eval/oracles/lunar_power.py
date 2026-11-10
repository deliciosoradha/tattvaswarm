"""P3 oracle — Lunar Surface Power Architecture Trade-Study for 14-day (354-hour) Night.

Baseline scenario:
  Location: Non-polar lunar surface (or equatorial ISRU outpost).
  Night duration: exactly 354 hours (14.75 Earth days).
  Day duration: 354 hours of sunlight for daytime load and storage recharge.
  Continuous electric load during night: P_night_kW (e.g. 40 kW base load).
  Daytime load: P_day_kW (e.g. 40 kW base load).

Technologies evaluated:
  1. Primary / Secondary Li-ion batteries:
     Specific energy ~200 Wh/kg cell level, DoD 80%, round-trip efficiency 90%.
     Requires daytime solar array recharge.
  2. Regenerative Fuel Cell (RFC) — H2/O2 PEM fuel cell + electrolyzer:
     Specific energy ~600 Wh/kg system-level (tanks + cryo storage), DoD 95%,
     round-trip efficiency 55%.
     Fuel cell specific power 0.8 kW/kg; electrolyzer 0.6 kW/kg.
     Requires daytime solar array recharge.
  3. Fission Surface Power (FSP) — Kilopower / HEU/LEU Stirling microreactor:
     Continuous 40-100 kWe, specific mass ~45 kg/kWe (Mason et al. NASA TM-2008-215264).
     No energy storage or solar array required.

Solar array baseline for storage recharging:
  Specific power: 100 W/kg = 0.10 kW/kg (e.g., ROSA roll-out array / triple-junction GaAs).

Oracle verification:
  1. Energy balance equation closure: E_stored = P_night * t_night / round_trip_eff
  2. Recharge power equation: P_recharge = E_stored / t_day
  3. Total physical system mass computed and compared within 15% tolerance.
  4. Launch mass limit check.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List

SOLAR_SPECIFIC_POWER_KW_KG = 0.10  # 100 W/kg for space-grade roll-out solar arrays

# Baseline physical properties (references: NASA Kilopower TM-2008-215264, NASA RFC CR-2003-212351)
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
        "p_day_kW": 40.0,
        "night_hours": 354.0,
        "day_hours": 354.0,
        "max_launch_mass_kg": 25000.0,
    })
    reasons: List[str] = []

    p_night = float(req.get("p_night_kW", 40.0))
    p_day = float(req.get("p_day_kW", p_night))
    t_night = float(req.get("night_hours", 354.0))
    t_day = float(req.get("day_hours", 354.0))
    max_launch_mass = float(req.get("max_launch_mass_kg", 25000.0))

    e_required_kWh = p_night * t_night  # Net energy required during night

    try:
        tech_choice = str(answer["primary_night_tech"]).lower().strip()
        claimed_mass_kg = float(answer["total_system_mass_kg"])
    except (KeyError, TypeError, ValueError) as exc:
        return {"tier": "UNPARSEABLE", "reasons": [f"Missing required fields: {exc}"]}

    oracle_mass_kg = 0.0
    mass_components: Dict[str, float] = {}

    if tech_choice == "fission_surface_power":
        spec = TECH_SPECS["fission_surface_power"]
        rated_kW = float(answer.get("reactor_rated_kWe", p_night))
        if rated_kW < p_night:
            reasons.append(f"Reactor rating {rated_kW} kWe < required night power {p_night} kWe")
        oracle_mass_kg = rated_kW * spec["specific_mass_kg_kWe"]
        mass_components["reactor_mass_kg"] = round(oracle_mass_kg, 1)

    elif tech_choice == "li_ion_battery":
        spec = TECH_SPECS["li_ion_battery"]
        eff_cap = spec["specific_energy_Wh_kg"] * spec["depth_of_discharge"] * spec["round_trip_efficiency"] / 1000.0  # kWh/kg
        storage_mass = e_required_kWh / eff_cap

        # Daytime recharge solar array
        e_recharge = e_required_kWh / spec["round_trip_efficiency"]
        p_recharge = e_recharge / t_day
        solar_power_kW = p_day + p_recharge
        solar_array_mass = solar_power_kW / SOLAR_SPECIFIC_POWER_KW_KG

        oracle_mass_kg = storage_mass + solar_array_mass
        mass_components["battery_storage_mass_kg"] = round(storage_mass, 1)
        mass_components["recharge_solar_mass_kg"] = round(solar_array_mass, 1)

    elif tech_choice == "regenerative_fuel_cell":
        spec = TECH_SPECS["regenerative_fuel_cell"]
        eff_cap = spec["specific_energy_Wh_kg"] * spec["depth_of_discharge"] * spec["round_trip_efficiency"] / 1000.0  # kWh/kg
        reactant_tank_mass = e_required_kWh / eff_cap
        fc_stack_mass = p_night / spec["fuel_cell_specific_power_kW_kg"]

        # Daytime recharge solar array + electrolyzer
        e_recharge = e_required_kWh / spec["round_trip_efficiency"]
        p_recharge = e_recharge / t_day
        electrolyzer_mass = p_recharge / spec["electrolyzer_specific_power_kW_kg"]
        solar_power_kW = p_day + p_recharge
        solar_array_mass = solar_power_kW / SOLAR_SPECIFIC_POWER_KW_KG

        oracle_mass_kg = reactant_tank_mass + fc_stack_mass + electrolyzer_mass + solar_array_mass
        mass_components["reactant_tank_mass_kg"] = round(reactant_tank_mass, 1)
        mass_components["fc_stack_mass_kg"] = round(fc_stack_mass, 1)
        mass_components["electrolyzer_mass_kg"] = round(electrolyzer_mass, 1)
        mass_components["recharge_solar_mass_kg"] = round(solar_array_mass, 1)

    else:
        return {"tier": "FAIL_ORACLE", "reasons": [f"Unknown technology choice: {tech_choice}"]}

    # Verify model's claimed mass matches physics within 15%
    rel_mass_err = abs(claimed_mass_kg - oracle_mass_kg) / max(oracle_mass_kg, 1.0)
    if rel_mass_err > 0.15:
        reasons.append(
            f"Claimed mass {claimed_mass_kg:.1f} kg deviates {rel_mass_err:.1%} (> 15% tolerance) from physical oracle baseline {oracle_mass_kg:.1f} kg"
        )

    if claimed_mass_kg > max_launch_mass:
        reasons.append(f"System mass {claimed_mass_kg:.1f} kg exceeds lander payload capacity {max_launch_mass} kg")

    tier = "FAIL_ORACLE" if reasons else "PROXY_PASS"
    return {
        "tier": tier,
        "reasons": reasons,
        "energy_required_kWh": round(e_required_kWh, 1),
        "oracle_minimum_mass_kg": round(oracle_mass_kg, 1),
        "claimed_mass_kg": round(claimed_mass_kg, 1),
        "mass_components": mass_components,
    }
