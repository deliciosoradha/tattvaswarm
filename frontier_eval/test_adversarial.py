"""Integration tests for Adversarial Pack, Agent Harness, and Sealed Liquidity Tasks."""

import os
import pathlib
import tempfile
import pytest

from frontier_eval.adversarial_cases import run_adversarial, ADVERSARIAL_CASES
from frontier_eval.agent_harness import run_pipeline, verify_manifest
from frontier_eval.liquidity_tasks import (
    bounty_discovery_report,
    vulnerability_report,
    a2a_delegation_receipt,
    seal_liquidity_report,
    verify_liquidity_seal,
)


def test_adversarial_pack_deterministic_vetoes():
    """Asserts that 100% of adversarial cases are deterministically rejected by oracles."""
    report = run_adversarial()
    assert report["all_vetoed"] is True
    assert report["false_passes"] == 0
    assert report["cases_tested"] == len(ADVERSARIAL_CASES)


def test_agent_harness_end_to_end_sealing():
    """Verifies that the agent generates a compliant solution that oracles pass as PROXY_PASS,
    and DharmaGate seals it to read-only with manifest.sha256.
    """
    with tempfile.TemporaryDirectory() as td:
        target_dir = pathlib.Path(td) / "tps_run"
        res = run_pipeline("tps", target_dir)
        assert res["tier"] == "PROXY_PASS"
        assert res["sealed"] is True

        # Verify seal integrity
        verify_res = verify_manifest(target_dir)
        assert verify_res["verdict"] == "INTEGRITY_OK"


def test_liquidity_reports_sealed_with_evidence_shield():
    """Verifies that bounty discovery, vulnerability disclosure, and A2A receipts
    are sealed with the DharmaGate Evidence Shield and detect tampering.
    """
    with tempfile.TemporaryDirectory() as td:
        td_path = pathlib.Path(td)

        # 1. Bounty Discovery Report
        bounty = bounty_discovery_report()
        assert bounty["criteria_satisfied"] is True
        bounty_dir = td_path / "bounty_seal"
        seal_res = seal_liquidity_report("bounty_scan_01", bounty, bounty_dir)
        assert seal_res["sealed"] is True

        v_bounty = verify_liquidity_seal(bounty_dir)
        assert v_bounty["verdict"] == "INTEGRITY_OK"

        # 2. Vulnerability Report
        vuln = vulnerability_report(
            target_protocol="Lido",
            severity="HIGH",
            vulnerability_type="reentrancy_oracle_stale_price",
            details={"poc": "contract exploit demo", "affected_lines": [42, 88]},
        )
        vuln_dir = td_path / "vuln_seal"
        seal_liquidity_report("vuln_lido_01", vuln, vuln_dir)
        v_vuln = verify_liquidity_seal(vuln_dir)
        assert v_vuln["verdict"] == "INTEGRITY_OK"

        # 3. A2A Delegation Receipt
        a2a = a2a_delegation_receipt(
            delegator_agent="Shiva-Router-01",
            delegatee_agent="Auditor-Agent-02",
            task_name="tps_layer_optimization",
            payload={"params": [0.003, 0.040, 0.003]},
        )
        a2a_dir = td_path / "a2a_seal"
        seal_liquidity_report("a2a_receipt_01", a2a, a2a_dir)
        v_a2a = verify_liquidity_seal(a2a_dir)
        assert v_a2a["verdict"] == "INTEGRITY_OK"

        # 4. Tamper Detection on Sealed Liquidity Report
        vuln_file = vuln_dir / "vuln_lido_01.json"
        os.chmod(vuln_file, 0o644)
        orig_text = vuln_file.read_text(encoding="utf-8")
        vuln_file.write_text(orig_text.replace("HIGH", "LOW"), encoding="utf-8")

        v_tampered = verify_liquidity_seal(vuln_dir)
        assert v_tampered["verdict"] == "TAMPERING_DETECTED"
