"""MCP server (stdio) — TattvaSwarm tools for any MCP client. stdlib only.

Run::

    python3 -m tattva_swarm.mcp_server

Tools exposed:

* ``tattva_status``         — honest backend snapshot (key / tiers / sandbox)
* ``tattva_route``          — one prompt through the tiered Nemotron router
* ``tattva_memory_add``     — store a note in the local memory (SQLite + FTS5)
* ``tattva_memory_search``  — full-text search over local memory
* ``tattva_swarm_run``      — run the logical swarm engine (Rust core if built)
* ``tattva_code_run``       — run a command in the hardened Docker sandbox

Protocol: JSON-RPC 2.0 over stdio, newline-delimited (MCP 2024-11-05).
stdout carries protocol messages only; diagnostics go to stderr.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any, Callable

from . import __version__

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "tattvaswarm", "version": __version__}
INSTRUCTIONS = (
    "Sovereign personal AI swarm: tiered NVIDIA Nemotron routing on Nebius "
    "Token Factory, local-only memory, logical worker swarms, and a hardened "
    "code sandbox. Nothing runs on the host; failures are reported honestly."
)

# ---------------------------------------------------------------------------
# tools
# ---------------------------------------------------------------------------


def _tool_status(args: dict) -> tuple[dict, bool]:
    import os

    from .muse_bridge import MuseSwarmAdapter
    from .nebius import load_env_file, tattva_home
    from .router import tier_models
    from .sandbox import backend_status

    load_env_file()
    key = os.environ.get("NEBIUS_API_KEY", "").strip()
    out = {
        "status": "ok",
        "api_key": f"set (len={len(key)})" if key else "missing — get one at https://tokenfactory.nebius.com/",
        "tiers": tier_models(),
        "research_tier": "enabled" if os.environ.get("TAVILY_API_KEY", "").strip() else "disabled (TAVILY_API_KEY missing)",
        "sandbox": backend_status(),
        "muse": MuseSwarmAdapter().status_snapshot(),
        "tattva_home": str(tattva_home()),
        "protocol": PROTOCOL_VERSION,
        "version": __version__,
    }
    return out, False


def _tool_route(args: dict) -> tuple[dict, bool]:
    prompt = str(args.get("prompt", "")).strip()
    if not prompt:
        return {"status": "error", "error": "missing required argument: prompt"}, True
    from .router import route

    out = route(
        prompt,
        tier=str(args.get("tier", "auto")),
        provider=str(args.get("provider", "auto")),
    )
    return out, out.get("status") != "ok"


def _tool_muse_route(args: dict) -> tuple[dict, bool]:
    import os
    import tempfile

    prompt = str(args.get("prompt", "")).strip()
    if not prompt:
        return {"status": "error", "error": "missing required argument: prompt"}, True
    from .muse_bridge import MuseSwarmAdapter

    with tempfile.TemporaryDirectory() as td:
        out = MuseSwarmAdapter(ledger_path=os.path.join(td, "mcp_ledger.json")).route_with_muse(
            prompt,
            task_id=int(args.get("task_id", 0)),
            modality=str(args.get("modality", "reasoning")),
            execute_live=bool(args.get("execute_live", False)),
        )
    return out, out.get("status") != "ok"


def _tool_muse_pipeline(args: dict) -> tuple[dict, bool]:
    import os
    import tempfile

    prompt = str(args.get("prompt", "")).strip()
    if not prompt:
        return {"status": "error", "error": "missing required argument: prompt"}, True
    from .muse_bridge import MuseSwarmAdapter

    with tempfile.TemporaryDirectory() as td:
        out = MuseSwarmAdapter(ledger_path=os.path.join(td, "mcp_ledger.json")).run_full_pipeline(
            prompt,
            agent_id=int(args.get("agent_id", 0)),
            dimension=int(args.get("dimension", 6)),
            task_type=str(args.get("task_type", "reasoning")),
            execute_live=bool(args.get("execute_live", False)),
        )
    return out, out.get("status") != "ok"


def _tool_muse_resume(args: dict) -> tuple[dict, bool]:
    import os
    import tempfile

    from .muse_bridge import DEFAULT_MUSE_SESSION_ID, MuseSwarmAdapter

    session_id = str(args.get("session_id") or DEFAULT_MUSE_SESSION_ID).strip()
    prompt = args.get("prompt")
    with tempfile.TemporaryDirectory() as td:
        out = MuseSwarmAdapter(ledger_path=os.path.join(td, "mcp_ledger.json")).resume_muse_session(
            session_id=session_id,
            prompt=str(prompt) if prompt is not None else None,
            execute_live=bool(args.get("execute_live", False)),
        )
    return out, out.get("status") != "ok"


def _tool_memory_add(args: dict) -> tuple[dict, bool]:
    text = str(args.get("text", "")).strip()
    if not text:
        return {"status": "error", "error": "missing required argument: text"}, True
    from .memory import Memory

    mem = Memory()
    try:
        entry_id = mem.add(
            text,
            kind=str(args.get("kind", "note")),
            source="mcp",
            tags=list(args.get("tags") or []) or None,
        )
        return {"status": "ok", "id": entry_id, "note": "stored locally; nothing left this machine"}, False
    finally:
        mem.close()


def _tool_memory_search(args: dict) -> tuple[dict, bool]:
    query = str(args.get("query", "")).strip()
    if not query:
        return {"status": "error", "error": "missing required argument: query"}, True
    from .memory import Memory

    mem = Memory()
    try:
        rows = mem.search(query, limit=int(args.get("limit", 5)))
        return {"status": "ok", "query": query, "count": len(rows), "results": rows}, False
    finally:
        mem.close()


def _tool_swarm_run(args: dict) -> tuple[dict, bool]:
    workers = max(1, int(args.get("workers", 100_000)))
    steps = max(1, int(args.get("steps", 6)))
    seed = int(args.get("seed", 7))
    modulus = max(2, int(args.get("modulus", 97)))
    threads = int(args.get("threads", 0))

    from .sandbox import find_engine_binary

    engine = find_engine_binary()
    if engine:
        argv = [engine, "run-swarm", "--workers", str(workers), "--steps", str(steps),
                "--seed", str(seed), "--modulus", str(modulus)]
        if threads > 0:
            argv += ["--threads", str(threads)]
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=600)
            payload = json.loads([ln for ln in proc.stdout.strip().splitlines() if ln.strip()][-1])
            payload["implementation"] = "rust"
            return payload, False
        except Exception as exc:  # noqa: BLE001 — fall through to the python reference
            sys.stderr.write(f"[tattva-mcp] rust swarm failed ({exc}); using python reference\n")

    from .engine import SwarmConfig, run_swarm

    report = run_swarm(SwarmConfig(workers=workers, steps=steps, seed=seed, solve_modulus=modulus))
    out = report.to_dict()
    out["implementation"] = "python"
    return out, False


def _tool_code_run(args: dict) -> tuple[dict, bool]:
    command = str(args.get("command", "")).strip()
    if not command:
        return {"status": "error", "error": "missing required argument: command"}, True
    from .sandbox import CodeEngineError, run_code

    try:
        result = run_code(
            command,
            image=args.get("image"),
            timeout_s=float(args.get("timeout_s", 30)),
            allow_network=bool(args.get("allow_network", False)),
            workdir=args.get("workdir"),
        )
    except CodeEngineError as exc:
        return {"status": "error", "error": str(exc)}, True
    return result.to_dict(), False


def _tool_frontier_oracle_eval(args: dict) -> tuple[dict, bool]:
    oracle_name = str(args.get("oracle", "")).lower().strip()
    task = args.get("task") or {}
    answer = args.get("answer") or {}

    try:
        from frontier_eval.oracles import scramjet, tps, lunar_power, rubisco, backtranslate
        dispatch = {
            "scramjet": scramjet,
            "tps": tps,
            "lunar_power": lunar_power,
            "rubisco": rubisco,
            "backtranslate": backtranslate,
        }
        if oracle_name not in dispatch:
            return {"status": "error", "error": f"unknown oracle: {oracle_name!r}. Choices: {list(dispatch.keys())}"}, True
        res = dispatch[oracle_name].evaluate(task, answer)
        return {"status": "ok", "oracle": oracle_name, "evaluation": res}, False
    except Exception as exc:
        return {"status": "error", "error": str(exc)}, True


def _tool_frontier_agent_harness(args: dict) -> tuple[dict, bool]:
    import pathlib
    import tempfile

    task_name = str(args.get("task", "tps")).lower().strip()
    agent_type = str(args.get("agent", "tattva")).lower().strip()
    evidence_dir_str = args.get("evidence_dir")

    try:
        from frontier_eval.agent_harness import default_agent, run_pipeline, tattva_agent

        agent_fn = tattva_agent if agent_type == "tattva" else default_agent
        if evidence_dir_str:
            evidence_dir = pathlib.Path(evidence_dir_str)
            res = run_pipeline(task_name, evidence_dir, agent_fn=agent_fn)
            return {"status": "ok", "result": res}, False
        else:
            with tempfile.TemporaryDirectory() as td:
                res = run_pipeline(task_name, pathlib.Path(td), agent_fn=agent_fn)
                return {"status": "ok", "result": res}, False
    except Exception as exc:
        return {"status": "error", "error": str(exc)}, True


def _tool_frontier_evidence_verify(args: dict) -> tuple[dict, bool]:
    import pathlib

    evidence_dir = str(args.get("evidence_dir", "")).strip()
    if not evidence_dir:
        return {"status": "error", "error": "missing required argument: evidence_dir"}, True
    try:
        from frontier_eval.agent_harness import verify_manifest

        res = verify_manifest(pathlib.Path(evidence_dir))
        return {"status": "ok", "verification": res}, False
    except Exception as exc:
        return {"status": "error", "error": str(exc)}, True


def _tool_frontier_treeseract_execute(args: dict) -> tuple[dict, bool]:
    import pathlib
    import tempfile
    from frontier_eval.treeseract_executor import TreeseractExecutor

    task_name = str(args.get("task", "tps")).lower().strip()
    dimension = int(args.get("dimension", 4))
    depth = int(args.get("depth", 2))
    branch_factor = int(args.get("branch_factor", 3))
    evidence_dir_str = args.get("evidence_dir")

    try:
        executor = TreeseractExecutor(
            task_name=task_name,
            dimension=dimension,
            max_depth=depth,
            branch_factor=branch_factor,
        )
        if evidence_dir_str:
            evidence_dir = pathlib.Path(evidence_dir_str)
            res = executor.run(evidence_dir=evidence_dir)
        else:
            with tempfile.TemporaryDirectory() as td:
                res = executor.run(evidence_dir=pathlib.Path(td))

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
        }, False
    except Exception as exc:
        return {"status": "error", "error": str(exc)}, True


def _tool_colab_bridge_status(args: dict) -> tuple[dict, bool]:
    import socket
    import urllib.request

    port = int(args.get("port", 9223))
    host = str(args.get("host", "127.0.0.1"))

    # Test local port
    is_open = False
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    try:
        res = sock.connect_ex((host, port))
        is_open = (res == 0)
    except Exception:
        pass
    finally:
        sock.close()

    colab_setup_snippet = (
        "!git clone https://github.com/deliciosoradha/tattvaswarm.git\n"
        "%cd tattvaswarm\n"
        "!pip install uv && uv run --with numpy,pytest pytest tests/ -q\n"
        "!PYTHONPATH=src:meta_hackathon_2026:. uv run --with numpy python3 -m frontier_eval.agent_harness --task all\n"
    )

    out = {
        "status": "ok",
        "bridge_target": f"{host}:{port}",
        "bridge_listening": is_open,
        "colab_ready": True,
        "setup_snippet": colab_setup_snippet,
    }
    return out, False


TOOLS: list[dict[str, Any]] = [
    {
        "name": "tattva_status",
        "description": "Honest snapshot of the TattvaSwarm stack: API key presence, tier models, code-engine backends, and Shiva-Muse status. Never fabricates.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "tattva_route",
        "description": "Route one prompt through the tiered NVIDIA Nemotron router on Nebius Token Factory or Shiva-Muse router (small/normal/reasoning/heavy/research/muse).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "The user prompt to route and answer."},
                "tier": {"type": "string", "enum": ["auto", "small", "normal", "reasoning", "heavy", "research", "muse"], "default": "auto"},
                "provider": {"type": "string", "enum": ["auto", "nebius", "muse"], "default": "auto"},
            },
            "required": ["prompt"],
            "additionalProperties": False,
        },
    },
    {
        "name": "tattva_muse_route",
        "description": "Route one prompt through ShivaMuseRouter with RTK secret redaction, Meru-Pingala Gray-code parity, and $100/$50 credit guardrail.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "modality": {"type": "string", "default": "reasoning"},
                "task_id": {"type": "integer", "default": 0},
                "execute_live": {"type": "boolean", "default": False},
            },
            "required": ["prompt"],
            "additionalProperties": False,
        },
    },
    {
        "name": "tattva_muse_pipeline",
        "description": "Run the 8-stage end-to-end Shiva-Muse verification pipeline (RTK -> Router -> Wonder Dream -> XDP Sensor -> Ashta-Gate -> SAM 3.1 -> Verifiable Harness).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "agent_id": {"type": "integer", "default": 0},
                "dimension": {"type": "integer", "default": 6},
                "task_type": {"type": "string", "default": "reasoning"},
                "execute_live": {"type": "boolean", "default": False},
            },
            "required": ["prompt"],
            "additionalProperties": False,
        },
    },
    {
        "name": "tattva_muse_resume",
        "description": "Resume a Meta Muse Code CLI UUIDv7 session (default 01a1c1c5-0154-7250-8767-f4beaff19eae) and export session trajectory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "default": "01a1c1c5-0154-7250-8767-f4beaff19eae"},
                "prompt": {"type": "string"},
                "execute_live": {"type": "boolean", "default": False},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "tattva_memory_add",
        "description": "Store a note in the local persistent memory (SQLite + FTS5). Data never leaves the machine.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "kind": {"type": "string", "default": "note"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "tattva_memory_search",
        "description": "Full-text search over the local memory (FTS5, operator-safe quoting).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 5},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "tattva_swarm_run",
        "description": "Run the deterministic logical swarm engine (Rust core when built, python reference otherwise). Same config -> same checksum.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workers": {"type": "integer", "minimum": 1, "default": 100000},
                "steps": {"type": "integer", "minimum": 1, "default": 6},
                "seed": {"type": "integer", "default": 7},
                "modulus": {"type": "integer", "minimum": 2, "default": 97},
                "threads": {"type": "integer", "minimum": 0, "default": 0},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "tattva_code_run",
        "description": "Run one command inside the hardened Docker sandbox (no network by default, memory/CPU caps, wall-clock timeout). Code never runs on the host.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run inside the sandbox image."},
                "image": {"type": "string", "description": "Container image (default python:3.12-slim or TATTVA_SANDBOX_IMAGE)."},
                "timeout_s": {"type": "number", "default": 30},
                "allow_network": {"type": "boolean", "default": False},
                "workdir": {"type": "string", "description": "Optional host dir mounted at /work (rw)."},
            },
            "required": ["command"],
            "additionalProperties": False,
        },
    },
    {
        "name": "frontier_oracle_eval",
        "description": "Evaluate an engineering candidate design against first-principles physics/biology oracles (scramjet, tps, lunar_power, rubisco, backtranslate). Never emits 'SOLVED'.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "oracle": {"type": "string", "enum": ["scramjet", "tps", "lunar_power", "rubisco", "backtranslate"]},
                "task": {"type": "object", "description": "Task constraints and requirements"},
                "answer": {"type": "object", "description": "Candidate design parameters to evaluate"},
            },
            "required": ["oracle", "answer"],
            "additionalProperties": False,
        },
    },
    {
        "name": "frontier_agent_harness",
        "description": "Run the complete Frontier Agent Harness: Agent Generates -> Oracle Qualifies -> DharmaGate Evidence Shield Seals (chmod 444 + manifest.sha256).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "enum": ["scramjet", "tps", "lunar_power", "rubisco", "backtranslate"], "default": "tps"},
                "agent": {"type": "string", "enum": ["tattva", "default"], "default": "tattva"},
                "evidence_dir": {"type": "string", "description": "Optional evidence directory path to write sealed bundle"},
            },
            "required": ["task"],
            "additionalProperties": False,
        },
    },
    {
        "name": "frontier_evidence_verify",
        "description": "Cryptographically verify the integrity of a sealed evidence bundle directory using DharmaGate Evidence Shield.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "evidence_dir": {"type": "string", "description": "Path to evidence bundle directory to verify"},
            },
            "required": ["evidence_dir"],
            "additionalProperties": False,
        },
    },
    {
        "name": "frontier_treeseract_execute",
        "description": "Execute Treeseract Search (MCTS on Meru Q_n Hypercube) with first-principles domain oracle pruning, Shiva reformulation, and DharmaGate sealing.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "enum": ["scramjet", "tps", "lunar_power", "rubisco", "backtranslate"], "default": "tps"},
                "dimension": {"type": "integer", "default": 4, "minimum": 2, "maximum": 10},
                "depth": {"type": "integer", "default": 2, "minimum": 1, "maximum": 5},
                "branch_factor": {"type": "integer", "default": 3, "minimum": 1, "maximum": 6},
                "evidence_dir": {"type": "string", "description": "Optional evidence directory path to write sealed bundle"},
            },
            "required": ["task"],
            "additionalProperties": False,
        },
    },
    {
        "name": "colab_bridge_status",
        "description": "Inspect the Google Colab integration bridge status and get the ready-to-run Colab setup commands.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "port": {"type": "integer", "default": 9223},
                "host": {"type": "string", "default": "127.0.0.1"},
            },
            "additionalProperties": False,
        },
    },
]

_HANDLERS: dict[str, Callable[[dict], tuple[dict, bool]]] = {
    "tattva_status": _tool_status,
    "tattva_route": _tool_route,
    "tattva_muse_route": _tool_muse_route,
    "tattva_muse_pipeline": _tool_muse_pipeline,
    "tattva_muse_resume": _tool_muse_resume,
    "tattva_memory_add": _tool_memory_add,
    "tattva_memory_search": _tool_memory_search,
    "tattva_swarm_run": _tool_swarm_run,
    "tattva_code_run": _tool_code_run,
    "frontier_oracle_eval": _tool_frontier_oracle_eval,
    "frontier_agent_harness": _tool_frontier_agent_harness,
    "frontier_evidence_verify": _tool_frontier_evidence_verify,
    "frontier_treeseract_execute": _tool_frontier_treeseract_execute,
    "colab_bridge_status": _tool_colab_bridge_status,
}

# ---------------------------------------------------------------------------
# JSON-RPC plumbing
# ---------------------------------------------------------------------------


def _result(mid: Any, payload: dict) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "result": payload}


def _error(mid: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def handle_message(msg: dict) -> dict | None:
    """Handle one JSON-RPC message; return a response dict, or None for notifications."""
    method = msg.get("method")
    mid = msg.get("id")

    if method == "initialize":
        return _result(mid, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
            "instructions": INSTRUCTIONS,
        })
    if method == "ping":
        return _result(mid, {})
    if method == "tools/list":
        return _result(mid, {"tools": TOOLS})
    if method == "tools/call":
        params = msg.get("params") or {}
        name = str(params.get("name", ""))
        args = params.get("arguments") or {}
        handler = _HANDLERS.get(name)
        if handler is None:
            return _result(mid, {
                "content": [{"type": "text", "text": f"unknown tool: {name!r}"}],
                "isError": True,
            })
        try:
            payload, is_err = handler(args)
        except Exception as exc:  # noqa: BLE001 — surface, never fake
            payload, is_err = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}, True
        return _result(mid, {
            "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}],
            "isError": is_err,
        })

    if mid is None:
        return None  # notification we don't handle (e.g. notifications/initialized)
    return _error(mid, -32601, f"method not found: {method}")


def main() -> int:
    sys.stderr.write(f"[tattva-mcp] serving over stdio (protocol {PROTOCOL_VERSION}, v{__version__})\n")
    sys.stderr.flush()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            sys.stderr.write("[tattva-mcp] dropped non-JSON line\n")
            continue
        response = handle_message(msg)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
