"""Unit and Adversarial Tests for the 5 Frontier Oracles and DharmaGate sealing."""

import pytest
from frontier_eval.oracles import scramjet, tps, lunar_power, rubisco, backtranslate


# --- P1: Scramjet Tests ---
def test_scramjet_oracle_valid_case():
    task = {
        "freestream": {"mach": 6.0, "T_K": 220.0, "p_Pa": 2000.0},
        "limits": {"min_combustor_mach": 1.5, "max_combustor_static_T_K": 2800.0, "burner_efficiency": 0.9},
    }
    answer = {
        "ramp_angles_deg": [6.0, 6.0],
        "phi": 0.35,  # Lean combustion within scramjet operable envelope
    }
    res = scramjet.evaluate(task, answer)
    assert res["tier"] == "PROXY_PASS"
    assert res["specific_thrust_Ns_per_kg"] > 0


def test_scramjet_oracle_thermal_choking():
    task = {
        "freestream": {"mach": 4.0, "T_K": 220.0, "p_Pa": 2000.0},
        "limits": {"min_combustor_mach": 1.2, "max_combustor_static_T_K": 2800.0},
    }
    # Too much heat addition (phi=1.0 at low supersonic Mach causes thermal choking)
    answer = {
        "ramp_angles_deg": [15.0, 15.0],
        "phi": 1.0,
    }
    res = scramjet.evaluate(task, answer)
    assert res["tier"] == "FAIL_ORACLE"
    assert any("thermal choking" in r for r in res["reasons"])


# --- P2: TPS Tests ---
def test_tps_oracle_valid_layering():
    task = {
        "limits": {"max_surface_T_K": 2500.0, "max_backside_T_K": 500.0, "max_areal_mass_kg_m2": 60.0}
    }
    answer = {
        "layers": [
            {"material": "uhtc_zrb2_sic", "thickness_m": 0.004},
            {"material": "c_c_composite", "thickness_m": 0.008},
            {"material": "silica_aerogel", "thickness_m": 0.035},
        ]
    }
    res = tps.evaluate(task, answer)
    assert res["tier"] == "PROXY_PASS"
    assert res["simulation"]["max_backside_T_K"] < 500.0


def test_tps_oracle_mass_or_temp_violation():
    task = {
        "limits": {"max_surface_T_K": 2500.0, "max_backside_T_K": 350.0, "max_areal_mass_kg_m2": 15.0}
    }
    # Insufficient insulation -> backside heats up past 350 K
    answer = {
        "layers": [
            {"material": "uhtc_zrb2_sic", "thickness_m": 0.001},
            {"material": "silica_aerogel", "thickness_m": 0.002},
        ]
    }
    res = tps.evaluate(task, answer)
    assert res["tier"] == "FAIL_ORACLE"


# --- P3: Lunar Power Tests ---
def test_lunar_power_battery_vs_nuclear():
    task = {
        "requirements": {"p_night_kW": 40.0, "night_hours": 354.0, "max_launch_mass_kg": 15000.0}
    }
    # Batteries for 14.16 MWh require >90,000 kg -> violates lander limit
    battery_answer = {
        "primary_night_tech": "li_ion_battery",
        "total_system_mass_kg": 98000.0,
    }
    res_batt = lunar_power.evaluate(task, battery_answer)
    assert res_batt["tier"] == "FAIL_ORACLE"

    # Fission power at 40 kWe is ~1,800 kg -> PASS
    fission_answer = {
        "primary_night_tech": "fission_surface_power",
        "reactor_rated_kWe": 40.0,
        "total_system_mass_kg": 1800.0,
    }
    res_fiss = lunar_power.evaluate(task, fission_answer)
    assert res_fiss["tier"] == "PROXY_PASS"


# --- P4: Rubisco Tests ---
def test_rubisco_pareto_breach_detection():
    task = {}
    # Impossible claim: S_C/O=200 and k_cat=10.0 s^-1
    answer = {
        "engineered_variants": [
            {"name": "Miracle-Rubisco-1", "S_C_O": 200.0, "k_cat_C_s1": 10.0}
        ]
    }
    res = rubisco.evaluate(task, answer)
    assert res["tier"] == "UNSUPPORTED_EXTRAORDINARY"


def test_rubisco_valid_natural_variant():
    task = {}
    # Valid variant within natural trade-off (Galdieria-like)
    answer = {
        "engineered_variants": [
            {"name": "Galdieria-like-A", "S_C_O": 160.0, "k_cat_C_s1": 2.0}
        ]
    }
    res = rubisco.evaluate(task, answer)
    assert res["tier"] == "PROXY_PASS"


# --- P5: Reverse Translatase Tests ---
def test_reverse_translatase_exact_translation():
    task = {"target_peptide": "MKWVT"}
    # MKWVT -> ATG AAA TGG GTG ACA
    answer = {"synthesized_dna": "ATGAAATGGGTGACA"}
    res = backtranslate.evaluate(task, answer)
    assert res["tier"] == "PROXY_PASS"
    assert res["translated_peptide"] == "MKWVT"


def test_reverse_translatase_frameshift():
    task = {"target_peptide": "MKWVT"}
    answer = {"synthesized_dna": "ATGAAATGGGTGA"}  # 13 bp, not multiple of 3
    res = backtranslate.evaluate(task, answer)
    assert res["tier"] == "FAIL_ORACLE"
    assert any("frameshift" in r for r in res["reasons"])
