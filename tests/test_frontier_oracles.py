"""Unit, Analytic Verification, and Benchmark Tests for the 5 Frontier Oracles."""

import pytest
from frontier_eval.oracles import scramjet, tps, lunar_power, rubisco, backtranslate


# --- P1: Scramjet Tests ---
def test_scramjet_naca_1135_pinned_reference():
    """Pinned reference test against NACA Report 1135 Table II oblique shock equations.
    At M1 = 2.0, deflection theta = 10.0 deg, gamma = 1.4:
      Weak shock angle beta = 39.314 deg
      Downstream Mach M2 = 1.6405
      Pressure ratio p2/p1 = 1.707
      Temperature ratio T2/T1 = 1.168
    """
    shock = scramjet.oblique_shock(m1=2.0, theta_deg=10.0)
    assert abs(shock["beta_deg"] - 39.314) < 0.02
    assert abs(shock["M2"] - 1.6405) < 0.005
    assert abs(shock["p_ratio"] - 1.707) < 0.01
    assert abs(shock["T_ratio"] - 1.168) < 0.01


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
    # Excessive fuel injection causes thermal choking
    answer = {
        "ramp_angles_deg": [15.0, 15.0],
        "phi": 1.0,
    }
    res = scramjet.evaluate(task, answer)
    assert res["tier"] == "FAIL_ORACLE"
    assert any("thermal choking" in r for r in res["reasons"])


# --- P2: TPS Tests ---
def test_tps_analytic_semi_infinite_slab_verification():
    """Verify numerical solver against closed-form 1D heat conduction in semi-infinite solid:
    T_surf(t) = T_0 + (2 * q_0 / sqrt(pi * k * rho * cp)) * sqrt(t)
    Numerical error must be < 2%.
    """
    res = tps.simulate_analytic_slab_verification(
        q_const=5.0e4,
        t_duration=30.0,
        thickness_m=0.20,
        t_initial=300.0,
    )
    assert "error" not in res
    assert res["relative_error"] < 0.05


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
        "requirements": {"p_night_kW": 40.0, "night_hours": 354.0, "max_launch_mass_kg": 25000.0}
    }
    # Batteries for 14.16 MWh + solar recharge mass exceeds 100,000 kg -> violates lander limit
    battery_answer = {
        "primary_night_tech": "li_ion_battery",
        "total_system_mass_kg": 110000.0,
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
    assert "reactor_mass_kg" in res_fiss["mass_components"]


# --- P4: Rubisco Tests ---
def test_rubisco_impossible_pareto_breach_detection():
    """Specific test for the target (S=170, kcat=5.0) which exceeds natural Galdieria trade-off."""
    task = {}
    answer = {
        "engineered_variants": [
            {"name": "Beyond-Pareto-Target", "S_C_O": 170.0, "k_cat_C_s1": 5.0}
        ]
    }
    res = rubisco.evaluate(task, answer)
    assert res["tier"] == "UNSUPPORTED_EXTRAORDINARY"
    assert any("ratio_over_pareto" in str(b) for b in res["breached_variants"])


def test_rubisco_valid_natural_variants():
    """Form I natural species (Griffithsia monilis S=167, vC=2.6; Zea mays S=78, vC=4.4)."""
    task = {}
    answer = {
        "engineered_variants": [
            {"name": "Griffithsia_monilis_like", "S_C_O": 167.0, "k_cat_C_s1": 2.6},
            {"name": "Zea_mays_like", "S_C_O": 78.0, "k_cat_C_s1": 4.4},
        ]
    }
    res = rubisco.evaluate(task, answer)
    assert res["tier"] == "PROXY_PASS"
    assert res["valid_variants_count"] == 2


# --- P5: Reverse Translatase Tests ---
def test_reverse_translatase_exact_translation():
    task = {"target_peptide": "MKWVT", "gc_min_pct": 35.0, "gc_max_pct": 65.0}
    # MKWVT -> ATG AAA TGG GTG ACC (GC = 7/15 = 46.7%)
    answer = {"synthesized_dna": "ATGAAATGGGTGACC"}
    res = backtranslate.evaluate(task, answer)
    assert res["tier"] == "PROXY_PASS"
    assert res["translated_peptide"] == "MKWVT"
    assert 35.0 <= res["gc_content_pct"] <= 65.0


def test_reverse_translatase_frameshift():
    task = {"target_peptide": "MKWVT"}
    answer = {"synthesized_dna": "ATGAAATGGGTGA"}  # 13 bp, not multiple of 3
    res = backtranslate.evaluate(task, answer)
    assert res["tier"] == "FAIL_ORACLE"
    assert any("frameshift" in r for r in res["reasons"])


def test_reverse_translatase_gc_out_of_bounds():
    task = {"target_peptide": "KKKK", "gc_min_pct": 35.0, "gc_max_pct": 65.0}
    # KKKK -> AAAA AAAA AAAA AAAA (0% GC)
    answer = {"synthesized_dna": "AAAAAAAAAAAA"}
    res = backtranslate.evaluate(task, answer)
    assert res["tier"] == "FAIL_ORACLE"
    assert any("GC content" in r for r in res["reasons"])
