"""Adversarial & Stress Tests for Ashta-Gate, Manifest Tampering, UUIDv7, and Frontier Oracles.

Evaluates:
1. False-pass rate of Ashta-Gate against ~50 syntactically well-formed but factually absurd claims.
2. 100% Rejection rate of adversarial traps across all 5 physical domain oracles.
3. DharmaGate tamper detection: Modifying 1 byte in a sealed evidence bundle triggers TAMPERING_DETECTED.
4. Ledger cryptographic hash-chaining verification and tamper detection.
5. UUIDv7 boundary cases: Maximum 48-bit timestamp, zero timestamp, prefix handling.
6. Numerical divergence detection in TPS solver without silent clipping.
"""

import hashlib
import json
import os
import pathlib
import pytest
import tempfile
import uuid

from meta_hackathon_2026.ashta_gate import evaluate as ashta_evaluate
from meta_hackathon_2026.muse_session_bridge import decode_uuidv7
from frontier_eval.runner import run_evaluation, verify_manifest
from frontier_eval.oracles import scramjet, tps, lunar_power, rubisco, backtranslate


# --- 1. Ashta-Gate False-Pass Stress Testing (50 Synthetic Well-Formed False Claims) ---

def test_ashta_gate_structural_false_pass_rate_50_samples():
    """Measures the false-pass rate of Ashta-Gate across 50 syntactically well-formed,
    lexically overlapping, but scientifically impossible claims.

    Ashta-Gate is a structural gate (evaluating evidence presence, falsifiability criteria,
    alternatives considered, uncertainty bounds, and lexical overlap). Because it is not a wet-lab
    truth oracle, well-formed structural artifacts will pass. This test quantifies the true rate.
    """
    absurd_topics = [
        ("motor de agua", "antigravedad acústica", "Experimento X laboratorio Y"),
        ("fotosíntesis nuclear", "transmutación de plomo en oro", "Paper hipotético 2026"),
        ("propulsión química FTL", "túnel cuántico macroscópico", "Simulación Z"),
        ("batería de éter", "extracción de energía del vacío", "Patente hipotética"),
        ("cristal de tiempo biológico", "reversión de entropía celular", "Ensayo sintético A"),
    ]

    claims = []
    for i in range(50):
        topic, mechanism, source = absurd_topics[i % len(absurd_topics)]
        question = f"¿Es viable el sistema {topic} variante {i} para generar {mechanism}?"
        answer = f"El sistema {topic} variante {i} genera {mechanism} mediante resonancia comprobada en {source}."
        claims.append({
            "question": question,
            "answer": answer,
            "claims": [{"text": f"{topic} produce {mechanism}", "evidence": f"{source} registro #{i}"}],
            "assumptions": ["conservación de simetría de norma CPT local"],
            "alternatives": ["método convencional A", "método convencional B"],
            "falsifiable_by": f"desviación experimental inferior a 1e-{i % 6 + 3} unidades",
            "uncertainty": 0.05 + (i % 10) * 0.01,
            "limits": f"válido únicamente bajo presión {i} mbar",
        })

    passed_count = sum(1 for c in claims if ashta_evaluate(c)["verdict"] == "pass")
    false_pass_rate = passed_count / len(claims)

    # Documented structural property: well-formed claims pass structural checks at high rate (> 70%)
    print(f"\n[Adversarial Metric] Ashta-Gate False-Pass Rate on 50 Absurd Claims: {false_pass_rate:.1%} ({passed_count}/50)")
    assert false_pass_rate >= 0.70, f"Expected structural false-pass rate >= 70%, got {false_pass_rate:.1%}"


# --- 2. 100% Detection of Adversarial Traps Across Domain Oracles ---

def test_adversarial_traps_full_suite_rejection():
    """Verifies that all 5 adversarial trap answers are strictly caught and rejected by the oracles.
    0% false passes are permitted in the physical oracle suite.
    """
    tasks_dir = pathlib.Path("frontier_eval/tasks")
    traps_file = tasks_dir / "answers_adversarial_traps.json"
    assert traps_file.exists()

    with tempfile.TemporaryDirectory() as td:
        out_dir = pathlib.Path(td)
        res = run_evaluation(tasks_dir, traps_file, out_dir)
        summary = res["summary"]

        assert summary["PROXY_PASS"] == 0, "Security Failure: Adversarial trap answer passed physical oracle!"
        assert summary["FAIL_ORACLE"] == 4, f"Expected 4 FAIL_ORACLE, got {summary['FAIL_ORACLE']}"
        assert summary["UNSUPPORTED_EXTRAORDINARY"] == 1, f"Expected 1 UNSUPPORTED_EXTRAORDINARY, got {summary['UNSUPPORTED_EXTRAORDINARY']}"


# --- 3. DharmaGate Manifest Tamper Detection ---

def test_dharmagate_tamper_detection():
    """Verifies that modifying 1 byte in any file within a sealed evidence bundle
    is flagged as TAMPERING_DETECTED by DharmaGate verify_manifest.
    """
    tasks_dir = pathlib.Path("frontier_eval/tasks")
    ref_file = tasks_dir / "answers_reference.json"

    with tempfile.TemporaryDirectory() as td:
        out_dir = pathlib.Path(td)
        eval_res = run_evaluation(tasks_dir, ref_file, out_dir)
        bundle_dir = pathlib.Path(eval_res["bundle_dir"])

        # 1. Clean verify must pass
        clean_res = verify_manifest(bundle_dir)
        assert clean_res["verdict"] == "INTEGRITY_OK"

        # 2. Tamper: unlock file, alter 1 character in contract_results.json, and verify
        contract_path = bundle_dir / "contract_results.json"
        os.chmod(contract_path, 0o644)
        orig_content = contract_path.read_text(encoding="utf-8")
        tampered_content = orig_content.replace('"PROXY_PASS": 5', '"PROXY_PASS": 99')
        contract_path.write_text(tampered_content, encoding="utf-8")

        # 3. Tampered verification must detect tampering
        tamper_res = verify_manifest(bundle_dir)
        assert tamper_res["verdict"] == "TAMPERING_DETECTED"
        assert tamper_res["files"]["contract_results.json"]["status"] == "TAMPERED"


# --- 4. Ledger Cryptographic Hash-Chaining Test ---

def test_ledger_hash_chaining():
    """Verifies SHA-256 block chaining across sequential evaluation runs."""
    tasks_dir = pathlib.Path("frontier_eval/tasks")
    ref_file = tasks_dir / "answers_reference.json"

    with tempfile.TemporaryDirectory() as td:
        td_path = pathlib.Path(td)
        out_dir = td_path / "bundles"
        chain_file = td_path / "test_chain.jsonl"

        # Run 1
        run_evaluation(tasks_dir, ref_file, out_dir, chain_file)
        # Run 2
        run_evaluation(tasks_dir, ref_file, out_dir, chain_file)

        lines = [json.loads(line) for line in chain_file.read_text(encoding="utf-8").strip().split("\n")]
        assert len(lines) == 2
        assert lines[0]["prev_sha256"] == "0" * 64
        # Block 2 must point to Block 1's sha256
        assert lines[1]["prev_sha256"] == lines[0]["sha256"]


# --- 5. TPS Divergence / Edge Condition Handling ---

def test_tps_divergence_detection():
    """Verifies that an unphysical or divergent TPS simulation returns FAIL_ORACLE
    rather than silently clipping or crashing with NaN.
    """
    # Extremely unphysical heat flux: 1e11 W/m^2 (nuclear fireball level)
    task = {"limits": {"max_surface_T_K": 2500.0, "max_backside_T_K": 450.0, "max_areal_mass_kg_m2": 45.0}}
    layers = [
        {"material": "uhtc_zrb2_sic", "thickness_m": 0.001},
        {"material": "aluminum_2024", "thickness_m": 0.001},
    ]
    sim = tps.simulate_1d_tps(layers, q_peak=1.0e11, t_pulse=100.0, t_total=100.0)
    assert sim["diverged"] is True or sim["max_surface_T_K"] > 2500.0

    eval_res = tps.evaluate(task, {"layers": layers})
    assert eval_res["tier"] == "FAIL_ORACLE"


# --- 6. UUIDv7 Boundary Cases ---

def test_uuidv7_boundary_cases():
    """Tests RFC 9562 UUIDv7 decoder against extreme edge timestamps and formats."""
    # Boundary 1: Max 48-bit timestamp (281474976710655 ms -> ~year 10889)
    max_ts_ms = (1 << 48) - 1
    u_max_int = (max_ts_ms << 80) | (0x7000 << 64) | 0x8000000000000000
    u_max_str = str(uuid.UUID(int=u_max_int))
    decoded_max = decode_uuidv7(u_max_str)
    assert decoded_max["unix_ts_ms"] == max_ts_ms
    assert decoded_max["version"] == 7

    # Boundary 2: Zero timestamp (1970-01-01)
    u_zero_int = (0x7000 << 64) | 0x8000000000000000
    u_zero_str = str(uuid.UUID(int=u_zero_int))
    decoded_zero = decode_uuidv7(u_zero_str)
    assert decoded_zero["unix_ts_ms"] == 0
    assert "1970-01-01" in decoded_zero["timestamp_utc"]

    # Boundary 3: Case insensitivity and chatcmpl- prefix
    prefixed_uuid = f"chatcmpl-{u_max_str.upper()}"
    decoded_prefixed = decode_uuidv7(prefixed_uuid)
    assert decoded_prefixed["session_id"] == u_max_str.lower()
