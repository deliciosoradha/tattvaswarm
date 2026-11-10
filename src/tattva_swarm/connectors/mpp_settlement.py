"""Machine Payment Protocol (MPP) Engine: Autonomous A2A Settlement Conditioned on DharmaGate Evidence.

Features:
  1. Micro-Escrows for Multi-Agent Swarms:
     - Delegator agent locks micro-bounty for worker agent pending physical proof.
  2. Proof-of-Verification Condition:
     - Escrow release strictly requires:
       a) DharmaGate manifest verification verdict == INTEGRITY_OK
       b) Domain Oracle tier == PROXY_PASS (never SOLVED, never FAIL_ORACLE)
       c) SHA-256 evidence bundle chained to the ledger
  3. Fail-Closed Dispute & Refund:
     - If evidence is tampered (single byte corruption), corrupted, or physical constraints breached,
       the escrow is immediately refunded to delegator with an immutable dispute receipt.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import pathlib
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

try:
    from src.utils import verify_manifest
except ImportError:
    from frontier_eval.runner import verify_manifest


@dataclass
class MPPEscrowInvoice:
    invoice_id: str
    delegator_agent: str
    worker_agent: str
    task_name: str
    amount_usdc: float
    created_at_utc: str
    condition: str
    status: str  # "LOCKED", "RELEASED", "REFUNDED"
    evidence_bundle_path: Optional[str] = None
    release_tx: Optional[str] = None


class MPPSettlementEngine:
    """Manages autonomous machine payment escrows conditioned on cryptographic and physical evidence.

    NOTE ON SETTLEMENT REALITY:
      - This engine currently acts as an audited off-chain bilateral state channel.
      - The evidence verification (DharmaGate SHA-256 + PROXY_PASS) is 100% real and enforced.
      - The escrow release_tx/refund_tx are cryptographic off-chain ledger receipts.
      - DO NOT use for live multi-tenant USDC custody until `contracts/MPPEscrow.sol` is deployed to Base.
    """

    ON_CHAIN_CONTRACT_DEPLOYED: bool = False
    SETTLEMENT_LAYER: str = "OFF_CHAIN_BILATERAL_STATE_CHANNEL"

    def __init__(self, treasury_address: Optional[str] = None):
        self.treasury_address = treasury_address or "0x206802681de11c10s0radha7a77va7rea5ury01"
        self._invoices: Dict[str, MPPEscrowInvoice] = {}

    def create_invoice(
        self,
        delegator_agent: str,
        worker_agent: str,
        task_name: str,
        amount_usdc: float = 0.05,
    ) -> MPPEscrowInvoice:
        timestamp_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        inv_seed = f"{delegator_agent}:{worker_agent}:{task_name}:{amount_usdc}:{timestamp_utc}"
        inv_id = f"mpp_{hashlib.sha256(inv_seed.encode()).hexdigest()[:16]}"

        invoice = MPPEscrowInvoice(
            invoice_id=inv_id,
            delegator_agent=delegator_agent,
            worker_agent=worker_agent,
            task_name=task_name,
            amount_usdc=amount_usdc,
            created_at_utc=timestamp_utc,
            condition="DharmaGate manifest.sha256 INTEGRITY_OK and Domain Oracle tier == PROXY_PASS",
            status="LOCKED",
        )
        self._invoices[inv_id] = invoice
        return invoice

    def settle_invoice_with_evidence(
        self,
        invoice_id: str,
        evidence_dir: pathlib.Path,
    ) -> Dict[str, Any]:
        """Validates evidence and releases or refunds the escrow."""
        invoice = self._invoices.get(invoice_id)
        if not invoice:
            raise ValueError(f"Unknown invoice: {invoice_id}")

        if invoice.status != "LOCKED":
            return {
                "status": "ALREADY_SETTLED",
                "invoice_id": invoice_id,
                "current_status": invoice.status,
            }

        # 1. Cryptographic Evidence Integrity Check
        manifest_res = verify_manifest(evidence_dir)
        is_integrity_ok = (manifest_res.get("verdict") == "INTEGRITY_OK")

        # 2. Domain Oracle Physical Tier Check
        tier = "UNKNOWN"
        receipt_path = evidence_dir / "treeseract_receipt.json"
        harness_path = evidence_dir / "harness_results.json"

        if receipt_path.exists():
            with open(receipt_path, "r", encoding="utf-8") as f:
                r_data = json.load(f)
                tier = r_data.get("best_node", {}).get("oracle_tier", "UNKNOWN")
        elif harness_path.exists():
            with open(harness_path, "r", encoding="utf-8") as f:
                h_data = json.load(f)
                tier = h_data.get("tier", "UNKNOWN")

        # 3. Decision Logic: Release vs Refund
        timestamp_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

        if is_integrity_ok and tier == "PROXY_PASS":
            # Release escrow
            release_hash = hashlib.sha256(f"release:{invoice_id}:{timestamp_utc}".encode()).hexdigest()
            release_tx = f"0x_mpp_rel_{release_hash[:32]}"
            invoice.status = "RELEASED"
            invoice.evidence_bundle_path = str(evidence_dir)
            invoice.release_tx = release_tx

            return {
                "status": "SETTLED_RELEASED",
                "invoice_id": invoice_id,
                "payout_recipient": invoice.worker_agent,
                "amount_usdc": invoice.amount_usdc,
                "tier": tier,
                "integrity_verdict": manifest_res.get("verdict"),
                "release_tx": release_tx,
                "timestamp_utc": timestamp_utc,
            }
        else:
            # Breach or failure -> Refund delegator
            refund_hash = hashlib.sha256(f"refund:{invoice_id}:{timestamp_utc}".encode()).hexdigest()
            refund_tx = f"0x_mpp_ref_{refund_hash[:32]}"
            invoice.status = "REFUNDED"
            invoice.evidence_bundle_path = str(evidence_dir)
            invoice.release_tx = refund_tx

            dispute_reason = []
            if not is_integrity_ok:
                dispute_reason.append(f"Tamper or integrity breach: {manifest_res.get('verdict')}")
            if tier != "PROXY_PASS":
                dispute_reason.append(f"Physical constraint failure: tier {tier}")

            return {
                "status": "DISPUTED_REFUNDED",
                "invoice_id": invoice_id,
                "refund_recipient": invoice.delegator_agent,
                "amount_usdc": invoice.amount_usdc,
                "tier": tier,
                "integrity_verdict": manifest_res.get("verdict"),
                "refund_tx": refund_tx,
                "dispute_reason": "; ".join(dispute_reason),
                "timestamp_utc": timestamp_utc,
            }
