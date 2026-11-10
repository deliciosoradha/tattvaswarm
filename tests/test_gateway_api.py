"""Integration & E2E tests for TattvaSwarm Production Gateway and Firebase CLI."""
from __future__ import annotations

import os
import pathlib
import pytest
from fastapi.testclient import TestClient

from tattva_swarm.gateway.api import app
from tattva_swarm.cli import main


@pytest.fixture
def client():
    return TestClient(app)


def test_healthz_endpoint(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "0.2.0"
    assert "tps" in data["oracles_available"]
    assert "scramjet" in data["oracles_available"]


def test_metrics_endpoint(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "total_active_challenges" in data
    assert "default_network" in data


def test_treeseract_search_unauthenticated_returns_402(client):
    payload = {"task": "tps", "dimension": 3, "depth": 1, "branch_factor": 2}
    response = client.post("/api/v1/treeseract/search", json=payload)
    assert response.status_code == 402
    assert "WWW-Authenticate" in response.headers
    assert response.headers["WWW-Authenticate"].startswith("x402")
    data = response.json()
    assert data["status"] == 402
    assert data["error"] == "Payment Required"
    assert "challenge" in data
    assert "challenge_id" in data["challenge"]
    assert float(data["challenge"]["amount"]) > 0


def test_treeseract_search_invalid_token_returns_402(client):
    payload = {"task": "tps", "dimension": 3, "depth": 1, "branch_factor": 2}
    headers = {"Authorization": "x402 tx=invalid_token_format"}
    response = client.post("/api/v1/treeseract/search", json=payload, headers=headers)
    assert response.status_code == 402
    data = response.json()
    assert "Payment Verification Failed" in data.get("error", "")


def test_treeseract_search_with_simulated_payment_succeeds(client):
    payload = {"task": "tps", "dimension": 3, "depth": 1, "branch_factor": 2}
    headers = {"Authorization": "x402 tx=0x_sim_gateway_test_token"}
    response = client.post("/api/v1/treeseract/search", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["task"] == "tps"
    assert "best_candidate" in data
    assert "best_tier" in data
    assert "payment_verification" in data
    assert data["payment_verification"].get("mode") == "simulated"


def test_frontier_eval_unauthenticated_returns_402(client):
    payload = {
        "oracle": "tps",
        "answer": {"thickness_m": 0.05, "material": "PICA-X", "roughness_um": 5.0},
    }
    response = client.post("/api/v1/frontier/eval", json=payload)
    assert response.status_code == 402


def test_frontier_eval_with_simulated_payment_succeeds(client):
    payload = {
        "oracle": "tps",
        "answer": {"thickness_m": 0.05, "material": "PICA-X", "roughness_um": 5.0},
    }
    headers = {"Authorization": "x402 tx=0x_sim_oracle_payment"}
    response = client.post("/api/v1/frontier/eval", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["oracle"] == "tps"
    assert "qualification" in data


def test_mpp_invoice_and_settle(client, tmp_path):
    # 1. Create MPP invoice
    inv_req = {
        "delegator": "Agent-Lead-01",
        "worker": "Agent-TPS-Worker",
        "task": "tps",
        "bounty": 0.10,
    }
    inv_res = client.post("/api/v1/mpp/invoice", json=inv_req)
    assert inv_res.status_code == 200
    inv_data = inv_res.json()
    invoice_id = inv_data["invoice_id"]
    assert invoice_id.startswith("mpp_")

    # 2. Run a small treeseract search to generate real sealed evidence
    evidence_dir = tmp_path / "test_evidence_dir"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    from frontier_eval.treeseract_executor import TreeseractExecutor
    executor = TreeseractExecutor(
        task_name="tps",
        dimension=3,
        max_depth=1,
        branch_factor=2,
        evidence_dir=evidence_dir,
    )
    executor.run()

    # 3. Settle MPP invoice
    settle_req = {
        "invoice_id": invoice_id,
        "evidence_dir": str(evidence_dir),
    }
    settle_res = client.post("/api/v1/mpp/settle", json=settle_req)
    assert settle_res.status_code == 200
    settle_data = settle_res.json()
    assert settle_data["status"] == "ok"
    assert settle_data["settlement"]["status"] == "SETTLED_RELEASED"
    assert "release_tx" in settle_data["settlement"]


def test_cdp_wallet_endpoint(client):
    response = client.get("/api/v1/cdp/wallet")
    assert response.status_code == 200
    data = response.json()
    assert "address" in data
    assert data["address"].startswith("0x")
    assert "balances" in data


def test_cli_firebase_status(capsys):
    ret = main(["firebase", "status"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "FIREBASE CONNECTOR STATUS" in captured.out


def test_cli_firebase_sync(capsys):
    ret = main(["firebase", "sync"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Synchronizing local ledger chain" in captured.out
