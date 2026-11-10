"""Unit and Integration Tests for Production Connectors: Firebase, x402 Gateway, and MPP Settlement."""

from __future__ import annotations

import pathlib
import tempfile
import json
import pytest

from src.tattva_swarm.connectors import (
    FirebaseConnector,
    X402Gateway,
    MPPSettlementEngine,
)
from frontier_eval.treeseract_executor import TreeseractExecutor


def test_firebase_connector_local_fallback_and_chain():
    """Verify FirebaseConnector functions transparently via local fallback when cloud SDK is offline."""
    with tempfile.TemporaryDirectory() as td:
        ledger_file = pathlib.Path(td) / "test_chain.jsonl"
        connector = FirebaseConnector(local_fallback_ledger=ledger_file)

        # 1. Sync evaluation run
        res = connector.sync_evaluation_run(
            run_id="run_test_001",
            task_name="tps",
            tier="PROXY_PASS",
            score=0.85,
            bundle_manifest={"REPORT.md": "a" * 64},
            receipt_data={"test": True},
            prev_sha256="0" * 64,
        )
        assert res["status"] in ("SYNCED", "LOCAL_SAVED")
        assert len(res["sha256"]) == 64
        assert ledger_file.exists()

        # 2. Get latest chain SHA-256
        latest_sha = connector.get_latest_chain_sha256()
        assert latest_sha == res["sha256"]

        # 3. Archive bundle
        dummy_dir = pathlib.Path(td) / "dummy_bundle"
        dummy_dir.mkdir()
        (dummy_dir / "REPORT.md").write_text("Test report", encoding="utf-8")
        arch = connector.archive_evidence_bundle(dummy_dir, "run_test_001")
        assert arch["status"] in ("UPLOADED", "LOCAL_ARCHIVED")
        assert len(arch["sha256"]) == 64


def test_x402_gateway_challenges_and_verification():
    """Verify HTTP 402 challenge generation, pricing table, and header verification."""
    gateway = X402Gateway(treasury_address="0xDeliciosoRadhaTreasury")

    # 1. Pricing check
    p_tps = gateway.get_service_price("treeseract", {"dimension": 4})
    assert p_tps == 0.10
    p_scram = gateway.get_service_price("oracle")
    assert p_scram == 0.02
    p_verify = gateway.get_service_price("verify")
    assert p_verify == 0.00

    # 2. Challenge creation
    quote = gateway.create_challenge("treeseract", "tps", {"dimension": 4})
    assert quote.amount_usdc == 0.10
    assert quote.recipient == "0xDeliciosoRadhaTreasury"
    assert quote.challenge_id.startswith("c_")

    # 3. HTTP 402 Response Payload
    code, headers, body = gateway.build_http_402_payload(quote)
    assert code == 402
    assert "WWW-Authenticate" in headers
    assert body["status"] == 402
    assert body["challenge"]["challenge_id"] == quote.challenge_id

    # 4. Payment verification: missing header
    ok, err, _ = gateway.verify_payment_header(None)
    assert ok is False
    assert "Missing" in err

    # 5. Payment verification: simulated / test token (only accepted with warning)
    auth_val = f"x402 tx=0x_sim_abc123:challenge={quote.challenge_id}"
    ok_sim, _, meta = gateway.verify_payment_header(auth_val, expected_challenge_id=quote.challenge_id)
    assert ok_sim is True
    assert meta["verified"] is True
    assert meta["mode"] == "simulated"
    assert "warning" in meta

    # 6. Payment verification: fake 66-char EVM hash MUST BE REJECTED by real Base RPC!
    fake_tx = "0x" + "a" * 64
    auth_fake = f"x402 tx={fake_tx}:challenge={quote.challenge_id}"
    ok_fake, err_fake, _ = gateway.verify_payment_header(auth_fake, expected_challenge_id=quote.challenge_id)
    assert ok_fake is False
    assert "not found on Base blockchain" in err_fake

    # 7. Payment verification: valid Base JSON-RPC receipt with matching USDC Transfer log
    valid_addr = "0x2068026810000000000000000000000000000001"
    gateway.treasury_address = valid_addr
    quote.recipient = valid_addr

    mock_receipt = {
        "status": "0x1",
        "blockNumber": "0x352cf8b",
        "gasUsed": "0x5208",
        "logs": [
            {
                "address": gateway.BASE_USDC_CONTRACT,
                "topics": [
                    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                    "0x0000000000000000000000001111111111111111111111111111111111111111",
                    "0x000000000000000000000000" + valid_addr[2:].lower(),
                ],
                "data": hex(int(quote.amount_usdc * 1e6)),
                "logIndex": "0x1",
            }
        ],
    }

    # Intercept rpc call by monkeypatching or testing internal method
    import unittest.mock as mock
    with mock.patch("urllib.request.urlopen") as mock_url:
        mock_resp = mock.MagicMock()
        mock_resp.read.return_value = json.dumps({"jsonrpc": "2.0", "result": mock_receipt}).encode()
        mock_url.return_value.__enter__.return_value = mock_resp

        ok_valid, msg_valid, meta_valid = gateway.verify_payment_header(
            f"x402 tx={'0x' + 'b'*64}:challenge={quote.challenge_id}",
            expected_challenge_id=quote.challenge_id,
        )
        assert ok_valid is True
        assert meta_valid["mode"] == "on_chain_confirmed"
        assert meta_valid["amount_usdc"] == quote.amount_usdc
        assert meta_valid["recipient"] == valid_addr.lower()


def test_mpp_settlement_engine_release_and_refund():
    """Verify MPP autonomous escrow releases on verified evidence and refunds on tampered evidence."""
    engine = MPPSettlementEngine()

    with tempfile.TemporaryDirectory() as td:
        ev_dir = pathlib.Path(td) / "treeseract_tps_sealed"

        # 1. Generate real sealed evidence using TreeseractExecutor
        executor = TreeseractExecutor(task_name="tps", dimension=3, max_depth=1, branch_factor=2)
        res = executor.run(evidence_dir=ev_dir)
        assert res.manifest_verdict in ("INTEGRITY_OK", "PASS")

        # 2. Create invoice
        inv = engine.create_invoice(
            delegator_agent="Agent-Wonder-01",
            worker_agent="Agent-Oracle-Worker",
            task_name="tps",
            amount_usdc=0.05,
        )
        assert inv.status == "LOCKED"

        # 3. Settle with valid evidence -> RELEASED
        settle_res = engine.settle_invoice_with_evidence(inv.invoice_id, ev_dir)
        assert settle_res["status"] == "SETTLED_RELEASED"
        assert settle_res["tier"] == "PROXY_PASS"
        assert settle_res["payout_recipient"] == "Agent-Oracle-Worker"
        assert "release_tx" in settle_res

    with tempfile.TemporaryDirectory() as td2:
        ev_dir2 = pathlib.Path(td2) / "tampered_bundle"
        ev_dir2.mkdir()
        (ev_dir2 / "REPORT.md").write_text("Tampered file", encoding="utf-8")
        (ev_dir2 / "manifest.sha256").write_text("badhash  REPORT.md\n", encoding="utf-8")

        inv2 = engine.create_invoice(
            delegator_agent="Agent-Wonder-01",
            worker_agent="Agent-Oracle-Worker",
            task_name="tps",
            amount_usdc=0.05,
        )
        # Settle with tampered evidence -> REFUNDED
        settle_res2 = engine.settle_invoice_with_evidence(inv2.invoice_id, ev_dir2)
        assert settle_res2["status"] == "DISPUTED_REFUNDED"
        assert settle_res2["refund_recipient"] == "Agent-Wonder-01"
        assert "Tamper or integrity breach" in settle_res2["dispute_reason"]
