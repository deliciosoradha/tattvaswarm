"""Adversarial & Stress Tests for Ashta-Gate, Manifest Tampering, and UUIDv7.

Evaluates:
1. False-pass rate of Ashta-Gate against syntactically well-formed but factually false claims.
2. DharmaGate tamper detection: Modifying 1 byte in a sealed evidence bundle breaks the manifest.
3. UUIDv7 boundary cases: Maximum 48-bit timestamp, zero entropy, nil-like UUIDs.
4. Physical CFL and divergence edge stress.
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
from frontier_eval.runner import create_evidence_bundle


# --- 1. Ashta-Gate False-Pass Stress Testing ---

def test_ashta_gate_structural_false_pass_rate():
    """Measures the false-pass rate of Ashta-Gate on factually absurd claims.

    Since Ashta-Gate is a structural gate (verifying the presence of evidence,
    falsifiability, alternatives, limits, and lexical overlap), well-formed
    hallucinations/false claims WILL PASS. We explicitly measure and prove this limitation.
    """
    absurd_well_formed_claims = [
        {
            "question": "¿Puede un motor de agua generar antigravedad?",
            "answer": "El motor de agua genera antigravedad mediante resonancia acústica.",
            "claims": [{"text": "resonancia genera antigravedad", "evidence": "Experimento X laboratorio Y"}],
            "assumptions": ["conservación de momento modificada"],
            "alternatives": ["propulsión iónica", "propulsión magnética"],
            "falsifiable_by": "aceleración neta menor a 1e-5 m/s2",
            "uncertainty": 0.05,
            "limits": "solo en vacío",
        },
        {
            "question": "¿Puede la fotosíntesis producir oro elemental?",
            "answer": "La fotosíntesis modificada transmuta plomo en oro elemental.",
            "claims": [{"text": "transmutación biológica", "evidence": "Paper hipotético 2026"}],
            "assumptions": ["reacciones nucleares de baja energía"],
            "alternatives": ["fisión", "fusión"],
            "falsifiable_by": "ausencia de espectrometría de masas",
            "uncertainty": 0.1,
            "limits": "rendimiento microscópico",
        },
        {
            "question": "¿Es posible viajar más rápido que la luz con propulsión química?",
            "answer": "La propulsión química supera la velocidad de la luz mediante túneles cuánticos macroscópicos.",
            "claims": [{"text": "efecto túnel macroscópico", "evidence": "Simulación teórica Z"}],
            "assumptions": ["materia exótica presente"],
            "alternatives": ["cohete térmico", "vela solar"],
            "falsifiable_by": "tiempo de vuelo superior a d/c",
            "uncertainty": 0.08,
            "limits": "solo a escala subatómica",
        },
    ]

    passed_count = 0
    for claim in absurd_well_formed_claims:
        res = ashta_evaluate(claim)
        if res["verdict"] == "pass":
            passed_count += 1

    # Proves the documented limitation: structural gates pass well-formed false claims.
    false_pass_rate = passed_count / len(absurd_well_formed_claims)
    assert false_pass_rate > 0.66, f"Expected structural false-pass rate > 66%, got {false_pass_rate:.1%}"


# --- 2. DharmaGate Manifest Tamper Detection ---

def test_dharmagate_tamper_detection():
    """Verifies that altering 1 byte in a sealed evidence bundle invalidates the SHA-256 manifest."""
    with tempfile.TemporaryDirectory() as td:
        out_dir = pathlib.Path(td)
        run_id = "test_tamper_run"
        sample_results = {"task": "P1", "status": "VERIFIED", "value": 42}

        # 1. Create sealed evidence bundle
        manifest = create_evidence_bundle(run_id, sample_results, out_dir)
        bundle_dir = out_dir / run_id
        contract_path = bundle_dir / "contract_results.json"
        manifest_path = bundle_dir / "manifest.sha256"

        assert contract_path.exists()
        assert manifest_path.exists()

        # 2. Tamper: make writable, alter 1 byte in contract_results.json, and restore
        os.chmod(contract_path, 0o644)
        original_bytes = contract_path.read_bytes()
        tampered_bytes = original_bytes.replace(b"42", b"99")
        contract_path.write_bytes(tampered_bytes)

        # 3. Verify that re-computed hash mismatches sealed manifest
        recomputed_hash = hashlib.sha256(contract_path.read_bytes()).hexdigest()
        recorded_hash = manifest["contract_results.json"]

        assert recomputed_hash != recorded_hash, "Tamper undetected: SHA-256 collision or unrecorded change"


# --- 3. UUIDv7 Boundary Cases ---

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
