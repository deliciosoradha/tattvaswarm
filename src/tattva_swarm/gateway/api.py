"""Production-Hardened HTTP API Gateway for TattvaSwarm, Treeseract, and Frontier Oracles.

Features:
  1. Sovereign Endpoints:
     - `GET /healthz`: Healthcheck, version, backend status, and uptime.
     - `GET /metrics`: Service execution metrics (runs, passes, gas, cache).
     - `POST /api/v1/treeseract/search`: High-performance MCTS search on Meru Q_n hypercube.
     - `POST /api/v1/frontier/eval`: First-principles domain oracle evaluation (P1-P5).
     - `GET /api/v1/evidence/verify/{task}`: Public free DharmaGate verification.
     - `POST /api/v1/mpp/invoice`: Autonomous A2A escrow invoice creation.
     - `POST /api/v1/mpp/settle`: Autonomous A2A escrow settlement.
     - `GET /api/v1/cdp/wallet`: Sovereign Agent Wallet info on Base.
  2. x402 Micropayment Enforcement Middleware:
     - Intercepts unauthenticated calls to paid services.
     - Returns HTTP 402 Payment Required with machine-readable challenge.
     - Validates on-chain transactions via Base JSON-RPC before executing workload.
"""
from __future__ import annotations

import datetime
import os
import pathlib
import sys
import time
from typing import Any, Dict, Optional

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from tattva_swarm.connectors import CDPConnector, MPPSettlementEngine, X402Gateway
from frontier_eval.treeseract_executor import TreeseractExecutor
from frontier_eval.agent_harness import ORACLE_DISPATCH, TASK_DEFAULTS

app = FastAPI(
    title="TattvaSwarm Production Gateway",
    version="0.2.0",
    description="Sovereign AI Swarm & Frontier Physical Oracles with x402 on-chain settlement on Base.",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

gateway = X402Gateway()
cdp = CDPConnector()
mpp = MPPSettlementEngine()

START_TIME = time.time()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TreeseractRequest(BaseModel):
    task: str = Field(default="tps", description="Frontier task name (scramjet, tps, lunar_power, rubisco, backtranslate)")
    dimension: int = Field(default=4, ge=2, le=8, description="Hypercube Q_n dimension")
    depth: int = Field(default=2, ge=1, le=4, description="Search tree depth")
    branch_factor: int = Field(default=3, ge=1, le=5, description="Branching factor")


class OracleEvalRequest(BaseModel):
    oracle: str = Field(description="scramjet, tps, lunar_power, rubisco, backtranslate")
    task: Dict[str, Any] = Field(default_factory=dict)
    answer: Dict[str, Any] = Field(description="Candidate design parameters")


class MPPInvoiceRequest(BaseModel):
    delegator: str = Field(default="Agent-Orchestrator-01")
    worker: str = Field(default="Agent-Oracle-Worker")
    task: str = Field(default="tps")
    bounty: float = Field(default=0.05, gt=0.0)


class MPPSettleRequest(BaseModel):
    invoice_id: str
    evidence_dir: str = Field(default="data/evidence/treeseract_tps")


# ---------------------------------------------------------------------------
# Middleware: x402 Payment Guard
# ---------------------------------------------------------------------------

@app.middleware("http")
async def x402_payment_middleware(request: Request, call_next):
    # Only protect paid computational endpoints
    paid_paths = ["/api/v1/treeseract/search", "/api/v1/frontier/eval"]
    if request.url.path in paid_paths and request.method == "POST":
        auth_header = request.headers.get("Authorization")
        req_challenge_id = request.headers.get("X-Challenge-Id")

        # Determine service key
        service_key = "treeseract" if "treeseract" in request.url.path else "oracle"

        # If no auth header, return HTTP 402 with fresh quote
        if not auth_header or not auth_header.strip().lower().startswith("x402"):
            quote = gateway.create_challenge(service=service_key, task="active_workload")
            status_code, headers, body = gateway.build_http_402_payload(quote)
            return Response(
                content=json_dumps(body),
                status_code=status_code,
                headers=headers,
                media_type="application/json",
            )

        # Validate provided payment token against real Base RPC (or simulation token if testing)
        is_valid, msg, meta = gateway.verify_payment_header(auth_header, expected_challenge_id=req_challenge_id)
        if not is_valid:
            quote = gateway.create_challenge(service=service_key, task="active_workload")
            _, headers, body = gateway.build_http_402_payload(quote)
            body["error"] = f"Payment Verification Failed: {msg}"
            return Response(
                content=json_dumps(body),
                status_code=402,
                headers=headers,
                media_type="application/json",
            )

        request.state.payment_meta = meta

    response = await call_next(request)
    return response


def json_dumps(obj: Any) -> str:
    import json
    return json.dumps(obj, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/healthz")
async def healthz():
    return {
        "status": "healthy",
        "service": "TattvaSwarm Production Gateway",
        "version": "0.2.0",
        "uptime_seconds": round(time.time() - START_TIME, 2),
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "oracles_available": list(ORACLE_DISPATCH.keys()),
    }


@app.get("/metrics")
async def metrics():
    return {
        "total_active_challenges": len(gateway._active_challenges),
        "total_invoices": len(mpp._invoices),
        "default_network": gateway.default_network,
        "treasury_address": gateway.treasury_address,
    }


@app.post("/api/v1/treeseract/search")
async def run_treeseract_search(req: TreeseractRequest, request: Request):
    try:
        executor = TreeseractExecutor(
            task_name=req.task,
            dimension=req.dimension,
            max_depth=req.depth,
            branch_factor=req.branch_factor,
        )
        res = executor.run()
        return {
            "status": "ok",
            "task": res.task_name,
            "best_node_id": res.best_node_id,
            "best_candidate": res.best_candidate,
            "best_tier": res.best_tier,
            "best_score": res.best_score,
            "total_nodes": res.total_nodes,
            "pruned_count": res.pruned_count,
            "trajectory": res.trajectory,
            "evidence_dir": res.evidence_dir,
            "manifest_verdict": res.manifest_verdict,
            "chain_sha256": res.chain_sha256,
            "payment_verification": getattr(request.state, "payment_meta", {}),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/frontier/eval")
async def run_frontier_eval(req: OracleEvalRequest, request: Request):
    oracle = ORACLE_DISPATCH.get(req.oracle)
    if not oracle:
        raise HTTPException(status_code=400, detail=f"Unknown oracle: {req.oracle}")

    task_def = req.task or TASK_DEFAULTS.get(req.oracle, {})
    result = oracle.evaluate(task_def, req.answer)
    return {
        "status": "ok",
        "oracle": req.oracle,
        "qualification": result,
        "payment_verification": getattr(request.state, "payment_meta", {}),
    }


@app.get("/api/v1/evidence/verify/{task_name}")
async def verify_task_evidence(task_name: str):
    from frontier_eval.agent_harness import verify_manifest
    target = pathlib.Path(f"data/evidence/treeseract_{task_name}")
    if not target.exists():
        target = pathlib.Path(f"data/evidence/{task_name}")
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Evidence directory not found for task: {task_name}")

    res = verify_manifest(target)
    return {"status": "ok", "task": task_name, "evidence_dir": str(target), "verification": res}


@app.post("/api/v1/mpp/invoice")
async def create_mpp_invoice(req: MPPInvoiceRequest):
    inv = mpp.create_invoice(
        delegator_agent=req.delegator,
        worker_agent=req.worker,
        task_name=req.task,
        amount_usdc=req.bounty,
    )
    return {
        "status": "ok",
        "invoice_id": inv.invoice_id,
        "delegator": inv.delegator_agent,
        "worker": inv.worker_agent,
        "task": inv.task_name,
        "bounty_usdc": inv.amount_usdc,
        "condition": inv.condition,
        "invoice_status": inv.status,
    }


@app.post("/api/v1/mpp/settle")
async def settle_mpp_invoice(req: MPPSettleRequest):
    try:
        res = mpp.settle_invoice_with_evidence(
            invoice_id=req.invoice_id,
            evidence_dir=pathlib.Path(req.evidence_dir),
        )
        return {"status": "ok", "settlement": res}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/v1/cdp/wallet")
async def get_cdp_wallet():
    w = cdp.get_or_create_wallet("base-mainnet")
    b = cdp.get_balance(w["address"], "base-mainnet")
    return {
        "address": w["address"],
        "network": w["network"],
        "chain_id": w["chain_id"],
        "balances": {
            "eth": b["eth_balance"],
            "usdc": b["usdc_balance"],
        },
        "rpc_status": b["rpc_connected"],
    }
