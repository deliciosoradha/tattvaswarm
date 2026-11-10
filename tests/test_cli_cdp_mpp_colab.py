"""End-to-End Tests for CDP CLI, MPP CLI, and Colab Bridge."""

from __future__ import annotations

import pathlib
import tempfile
import pytest

from src.tattva_swarm.cli import main as cli_main
from src.tattva_swarm.mcp_server import (
    _tool_cdp_wallet_info,
    _tool_cdp_wallet_balance,
    _tool_cdp_pay_x402,
    _tool_mpp_create_invoice,
    _tool_mpp_settle_invoice,
    _tool_colab_cell_generate,
)
from frontier_eval.treeseract_executor import TreeseractExecutor


def test_cli_colab_status_and_cell():
    """Verify `tattva colab status` and `tattva colab cell` commands."""
    assert cli_main(["colab", "status", "--port", "9223"]) == 0
    assert cli_main(["colab", "cell"]) == 0


def test_cli_cdp_wallet_and_balance():
    """Verify `tattva cdp wallet`, `balance`, and `faucet` commands."""
    assert cli_main(["cdp", "wallet", "--network", "base-mainnet"]) == 0
    assert cli_main(["cdp", "balance", "--network", "base-mainnet"]) == 0
    assert cli_main(["cdp", "faucet"]) == 0


def test_cli_cdp_pay():
    """Verify `tattva cdp pay` command generates signed x402 receipt."""
    code = cli_main(["cdp", "pay", "--challenge-id", "c_test_123", "--amount", "0.05"])
    assert code == 0


def test_cli_mpp_invoice_and_settle():
    """Verify `tattva mpp invoice` and `tattva mpp settle` commands with real evidence."""
    with tempfile.TemporaryDirectory() as td:
        ev_dir = pathlib.Path(td) / "treeseract_mpp_test"
        # 1. Run Treeseract to produce real sealed evidence
        executor = TreeseractExecutor(task_name="tps", dimension=3, max_depth=1, branch_factor=2)
        res = executor.run(evidence_dir=ev_dir)
        assert res.manifest_verdict in ("INTEGRITY_OK", "PASS")

        # 2. Test invoice creation
        code_inv = cli_main(["mpp", "invoice", "--task", "tps", "--bounty", "0.05"])
        assert code_inv == 0

        # 3. Test settlement
        code_settle = cli_main(["mpp", "settle", "--invoice-id", "mpp_test_inv_01", "--evidence-dir", str(ev_dir)])
        assert code_settle == 0


def test_mcp_cdp_and_mpp_and_colab_tools():
    """Verify MCP tools for CDP, MPP, and Colab."""
    # 1. CDP tools
    w_res, w_err = _tool_cdp_wallet_info({"network": "base-mainnet"})
    assert w_err is False
    assert "address" in w_res["wallet"]
    assert "private_key" not in w_res["wallet"]

    b_res, b_err = _tool_cdp_wallet_balance({"network": "base-mainnet"})
    assert b_err is False
    assert "eth_balance" in b_res["balance"]
    assert "usdc_balance" in b_res["balance"]

    p_res, p_err = _tool_cdp_pay_x402({"challenge_id": "c_mcp_999", "amount": 0.05})
    assert p_err is False
    assert p_res["payment"]["status"] == "PAID"
    assert "x402 tx=" in p_res["payment"]["auth_header"]

    # 2. MPP tools
    inv_res, inv_err = _tool_mpp_create_invoice({"task": "scramjet", "bounty": 0.08})
    assert inv_err is False
    assert inv_res["invoice"]["task"] == "scramjet"
    assert inv_res["invoice"]["amount_usdc"] == 0.08

    # 3. Colab tool
    c_res, c_err = _tool_colab_cell_generate({"task": "tps"})
    assert c_err is False
    assert "colab_cell" in c_res
    assert "!pip install uv" in c_res["colab_cell"]
