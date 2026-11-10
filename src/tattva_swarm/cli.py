"""TattvaSwarm CLI — `tattva <command>`.

Commands:
  tattva doctor                          env + backend health check (honest, never fakes OK)
  tattva route "prompt" [--tier T]       route one prompt through the tiered router
  tattva memory add|search|recent|count  local persistent memory
  tattva swarm run tasks.json            parallel -> verify -> synthesize (conductor)
  tattva code run "cmd"                  run one command in the hardened sandbox
  tattva mcp                             serve MCP tools over stdio
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__
from .nebius import BackendError, TokenFactoryClient, load_env_file, tattva_home
from .router import EXTENDED_TIERS, TIERS, route, tier_models


def cmd_doctor(_args: argparse.Namespace) -> int:
    load_env_file()
    print(f"TattvaSwarm {__version__} — doctor")
    key = os.environ.get("NEBIUS_API_KEY", "").strip()
    base = os.environ.get("NEBIUS_BASE_URL", "").strip() or "(default)"
    print(f"  NEBIUS_API_KEY: {'set (len=%d)' % len(key) if key else 'MISSING — get one at https://tokenfactory.nebius.com/'}")
    print(f"  NEBIUS_BASE_URL: {base}")
    for tier, model in tier_models().items():
        print(f"  tier {tier:<9}: {model or 'MISSING (set TATTVA_MODEL_* in .env)'}")
    print(f"  TATTVA_HOME: {tattva_home()}")
    tavily = "set" if os.environ.get("TAVILY_API_KEY", "").strip() else "not set (research tier disabled)"
    print(f"  TAVILY_API_KEY: {tavily}")
    try:
        from .muse_bridge import MuseSwarmAdapter

        muse_stat = MuseSwarmAdapter().status_snapshot()
        print(f"  SHIVA_MUSE: enabled (default_session={muse_stat['default_session_id']})")
    except Exception:
        pass
    if not key:
        print("  backend: SKIPPED (no key) — honest state, nothing was fabricated")
        return 2
    try:
        models = TokenFactoryClient().list_models()
        nvidia = [m for m in models if "nemotron" in m.lower() or m.lower().startswith("nvidia/")]
        print(f"  backend: OK — {len(models)} models visible, {len(nvidia)} nvidia/nemotron")
        return 0
    except BackendError as exc:
        print(f"  backend: FAIL — {exc}")
        return 1


def cmd_route(args: argparse.Namespace) -> int:
    out = route(
        args.prompt,
        tier=args.tier,
        provider=getattr(args, "provider", "auto"),
    )
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if out.get("status") == "ok" else 3


def cmd_muse(args: argparse.Namespace) -> int:
    import tempfile
    from .muse_bridge import DEFAULT_MUSE_SESSION_ID, MuseSwarmAdapter

    with tempfile.TemporaryDirectory() as td:
        adapter = MuseSwarmAdapter(ledger_path=os.path.join(td, "cli_ledger.json"))
        subcmd = getattr(args, "muse_cmd", None) or "resume"
        if subcmd == "route":
            out = adapter.route_with_muse(
                args.prompt,
                task_id=args.task_id,
                modality=args.modality,
                execute_live=args.live,
            )
        elif subcmd == "pipeline":
            out = adapter.run_full_pipeline(
                args.prompt,
                agent_id=args.agent_id,
                task_type=args.task_type,
                execute_live=args.live,
            )
        elif subcmd == "resume":
            out = adapter.resume_muse_session(
                session_id=getattr(args, "session_id", None) or DEFAULT_MUSE_SESSION_ID,
                prompt=getattr(args, "prompt", None),
                execute_live=getattr(args, "live", False),
            )
        elif subcmd == "dream":
            out = adapter.wonder_manifest(args.question, n=args.candidates)
        elif subcmd == "gate":
            trace = json.loads(args.trace_json)
            out = adapter.evaluate_ashta_gate(trace)
        else:
            print(f"unknown muse command {subcmd!r}", file=sys.stderr)
            return 2
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


def cmd_memory(args: argparse.Namespace) -> int:
    from .memory import Memory

    mem = Memory()
    try:
        if args.mem_cmd == "add":
            entry_id = mem.add(" ".join(args.text), kind=args.kind, tags=args.tags)
            print(f"added entry #{entry_id} (local only)")
            return 0
        if args.mem_cmd == "search":
            rows = mem.search(" ".join(args.query), limit=args.limit)
            if not rows:
                print("(no matches)")
                return 0
            for r in rows:
                print(f"#{r['id']} [{r['kind']}] {r['created_at']}  {r['text'][:140]}")
            return 0
        if args.mem_cmd == "recent":
            for r in mem.recent(limit=args.limit):
                print(f"#{r['id']} [{r['kind']}] {r['created_at']}  {r['text'][:140]}")
            return 0
        if args.mem_cmd == "count":
            print(f"{mem.count()} entries in {mem.path}")
            return 0
        print(f"unknown memory command {args.mem_cmd!r}", file=sys.stderr)
        return 2
    finally:
        mem.close()


def cmd_swarm(args: argparse.Namespace) -> int:
    from .conductor import run_graph

    spec = json.loads(open(args.spec, encoding="utf-8").read())
    out = run_graph(spec)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if all(r.get("status") == "ok" for r in out.get("results", [])) else 3


def cmd_code(args: argparse.Namespace) -> int:
    from .sandbox import CodeEngineError, run_code

    try:
        result = run_code(
            args.cmd,
            image=args.image,
            timeout_s=args.timeout,
            allow_network=args.allow_network,
            workdir=args.workdir,
        )
    except CodeEngineError as exc:
        print(f"code engine unavailable: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        print(
            f"[code-engine] backend={result.backend} exit={result.exit_code} "
            f"timed_out={result.timed_out} wall={result.wall_s}s",
            file=sys.stderr,
        )
    return result.exit_code if result.exit_code >= 0 else 1


def cmd_mcp(_args: argparse.Namespace) -> int:
    from .mcp_server import main as mcp_main

    return mcp_main()


def cmd_frontier(args: argparse.Namespace) -> int:
    subcmd = getattr(args, "frontier_cmd", "harness")
    if subcmd == "harness":
        import pathlib
        from frontier_eval.agent_harness import default_agent, run_pipeline, tattva_agent, ORACLE_DISPATCH

        agent_fn = tattva_agent if args.agent == "tattva" else default_agent
        evidence_path = pathlib.Path(args.evidence_dir)
        tasks_to_run = list(ORACLE_DISPATCH.keys()) if args.task == "all" else [args.task]

        print(f"[*] Frontier Agent Harness (Agent: {args.agent})")
        for tname in tasks_to_run:
            target_dir = evidence_path / tname if len(tasks_to_run) > 1 else evidence_path
            res = run_pipeline(tname, target_dir, agent_fn=agent_fn)
            print(f"[OK] Task `{tname}` -> Tier: {res['tier']} | Sealed at: {res['evidence_dir']}")
        return 0

    elif subcmd == "verify":
        import pathlib
        from frontier_eval.agent_harness import verify_manifest

        target = pathlib.Path(args.evidence_dir)
        print(f"[*] Verifying evidence directory: {target}")
        res = verify_manifest(target)
        print(f"[Result] Verdict: {res.get('verdict')}")
        for fname, info in res.get("files", {}).items():
            print(f"  - {fname}: {info.get('status')}")
        return 0 if res.get("verdict") == "INTEGRITY_OK" else 1

    elif subcmd == "adversarial":
        from frontier_eval.adversarial_cases import run_adversarial

        report = run_adversarial(getattr(args, "task", None))
        print("=" * 60)
        print("FRONTIER ADVERSARIAL VETO PACK REPORT")
        print("=" * 60)
        print(f"Total Cases: {report['cases_tested']} | False Passes: {report['false_passes']}")
        print(f"Overall Veto Success: {'PASS (All Rejected)' if report['all_vetoed'] else 'FAIL (Leak Detected)'}")
        print("-" * 60)
        for name, r in report["results"].items():
            status = "REJECTED (OK)" if r["veto_successful"] else "LEAKED"
            print(f"[{status}] {name:15}: {r['tier']} -> {r['violation']}")
    elif subcmd == "treeseract":
        import pathlib
        from frontier_eval.treeseract_executor import TreeseractExecutor

        task = getattr(args, "task", "tps")
        dimension = getattr(args, "dimension", 4)
        max_depth = getattr(args, "depth", 2)
        branch_factor = getattr(args, "branch_factor", 3)
        evidence_dir = pathlib.Path(args.evidence_dir) if getattr(args, "evidence_dir", None) else None

        print(f"[*] Launching Treeseract Executor for `{task}` (Q_{dimension} Hypercube, Depth {max_depth})...")
        executor = TreeseractExecutor(
            task_name=task,
            dimension=dimension,
            max_depth=max_depth,
            branch_factor=branch_factor,
        )
        res = executor.run(evidence_dir=evidence_dir)
        print("=" * 60)
        print(f"TREESERACT EXECUTION SUMMARY — {task.upper()}")
        print("=" * 60)
        print(f"Total Nodes Explored : {res.total_nodes}")
        print(f"Pruned by Physics   : {res.pruned_count}")
        print(f"Winning Node ID      : N{res.best_node_id}")
        print(f"Winning Oracle Tier  : {res.best_tier}")
        print(f"Physical Score       : {res.best_score:.4f}")
        print(f"Trajectory           : {' -> '.join(f'N{n}' for n in res.trajectory)}")
        print(f"Evidence Sealed At   : {res.evidence_dir}")
        print(f"Manifest Integrity   : {res.manifest_verdict}")
        if res.chain_sha256:
            print(f"Chain SHA-256        : {res.chain_sha256}")
        print("=" * 60)
        return 0 if res.manifest_verdict in ("INTEGRITY_OK", "PASS") else 1

    else:
        print(f"unknown frontier subcommand: {subcmd!r}", file=sys.stderr)
        return 2


def cmd_colab(args: argparse.Namespace) -> int:
    subcmd = getattr(args, "colab_cmd", "status")
    if subcmd == "status":
        import socket

        port = args.port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.0)
        is_open = False
        try:
            res = sock.connect_ex(("127.0.0.1", port))
            is_open = (res == 0)
        except Exception:
            pass
        finally:
            sock.close()

        print(f"Colab Bridge Status:")
        print(f"  Local Port 127.0.0.1:{port}: {'ACTIVE' if is_open else 'NOT LISTENING'}")
        print(f"  Ready for Colab MCP client connection.")
        return 0

    elif subcmd == "cell":
        colab_code = (
            "# --- TattvaSwarm Google Colab Quickstart Cell ---\n"
            "# Run this cell in any Google Colab notebook (CPU or T4/L4 GPU)\n"
            "!pip install uv\n"
            "!git clone https://github.com/deliciosoradha/tattvaswarm.git /content/tattvaswarm 2>/dev/null || (cd /content/tattvaswarm && git pull)\n"
            "%cd /content/tattvaswarm\n"
            "!uv run --with numpy,pytest pytest tests/ -q\n"
            "# Run all 5 frontier physical oracles through agent harness\n"
            "!PYTHONPATH=src:meta_hackathon_2026:. uv run --with numpy python3 -m frontier_eval.agent_harness --task all --evidence-dir /content/evidence\n"
            "# Verify sealed evidence manifest\n"
            "!PYTHONPATH=src:meta_hackathon_2026:. uv run --with numpy python3 -m frontier_eval.agent_harness verify /content/evidence/tps\n"
        )
        print(colab_code)
        return 0

    else:
        print(f"unknown colab subcommand: {subcmd!r}", file=sys.stderr)
        return 2


def cmd_cdp(args: argparse.Namespace) -> int:
    from .connectors.cdp_connector import CDPConnector

    subcmd = getattr(args, "cdp_cmd", "wallet")
    connector = CDPConnector()

    if subcmd == "wallet":
        network = getattr(args, "network", "base-mainnet")
        wallet = connector.get_or_create_wallet(network)
        print("=" * 60)
        print("CDP / BASE SOVEREIGN AGENT WALLET")
        print("=" * 60)
        print(f"Address    : {wallet['address']}")
        print(f"Network    : {wallet['network']} (Chain ID: {wallet['chain_id']})")
        print(f"Provider   : {wallet.get('provider', 'CDP_Sovereign_AgentKit')}")
        print(f"Created At : {wallet.get('created_at_utc')}")
        print("=" * 60)
        return 0

    elif subcmd == "balance":
        address = getattr(args, "address", None)
        network = getattr(args, "network", "base-mainnet")
        bal = connector.get_balance(address, network)
        print("=" * 60)
        print(f"WALLET BALANCE ({bal['network'].upper()})")
        print("=" * 60)
        print(f"Address      : {bal['address']}")
        print(f"ETH Balance  : {bal['eth_balance']:.6f} ETH")
        print(f"USDC Balance : {bal['usdc_balance']:.4f} USDC")
        print(f"RPC Endpoint : {bal['rpc_endpoint']}")
        print(f"RPC Live     : {'YES' if bal['rpc_connected'] else 'NO (Simulated/Offline)'}")
        print("=" * 60)
        return 0

    elif subcmd == "faucet":
        address = getattr(args, "address", None)
        network = getattr(args, "network", "base-sepolia")
        res = connector.request_faucet(address, network)
        print("=" * 60)
        print(f"BASE SEPOLIA FAUCET REQUEST")
        print("=" * 60)
        print(f"Recipient : {res['recipient']}")
        print(f"Granted   : {res['granted_eth']} ETH + {res['granted_usdc']} USDC")
        print(f"Tx Hash   : {res['tx_hash']}")
        print(f"Status    : {res['status']}")
        print("=" * 60)
        return 0

    elif subcmd == "pay":
        cid = getattr(args, "challenge_id", "")
        amount = float(getattr(args, "amount", 0.05))
        recipient = getattr(args, "recipient", "0xDeliciosoRadhaTreasury")
        res = connector.pay_x402_challenge(cid, amount, recipient)
        print("=" * 60)
        print("x402 PAYMENT EXECUTED")
        print("=" * 60)
        print(f"Challenge ID : {res['challenge_id']}")
        print(f"Sender       : {res['sender']}")
        print(f"Recipient    : {res['recipient']}")
        print(f"Amount USDC  : {res['amount_usdc']:.4f}")
        print(f"Tx Hash      : {res['tx_hash']}")
        print(f"Auth Header  : {res['auth_header']}")
        print("=" * 60)
        return 0

    else:
        print(f"unknown cdp subcommand: {subcmd!r}", file=sys.stderr)
        return 2


def cmd_mpp(args: argparse.Namespace) -> int:
    from .connectors.mpp_settlement import MPPSettlementEngine
    import pathlib

    subcmd = getattr(args, "mpp_cmd", "invoice")
    engine = MPPSettlementEngine()

    if subcmd == "invoice":
        delegator = getattr(args, "delegator", "Agent-Orchestrator-01")
        worker = getattr(args, "worker", "Agent-Oracle-Worker")
        task = getattr(args, "task", "tps")
        bounty = float(getattr(args, "bounty", 0.05))
        inv = engine.create_invoice(delegator, worker, task, bounty)
        print("=" * 60)
        print("MPP A2A ESCROW INVOICE CREATED")
        print("=" * 60)
        print(f"Invoice ID : {inv.invoice_id}")
        print(f"Delegator  : {inv.delegator_agent}")
        print(f"Worker     : {inv.worker_agent}")
        print(f"Task Name  : {inv.task_name}")
        print(f"Bounty     : {inv.amount_usdc:.4f} USDC")
        print(f"Status     : {inv.status}")
        print(f"Condition  : {inv.condition}")
        print("=" * 60)
        return 0

    elif subcmd == "settle":
        inv_id = getattr(args, "invoice_id", "")
        evidence_dir = pathlib.Path(getattr(args, "evidence_dir", "data/evidence/treeseract_tps"))
        if inv_id not in engine._invoices:
            inv = engine.create_invoice("Agent-Orchestrator-01", "Agent-Oracle-Worker", "tps", 0.05)
            inv_id = inv.invoice_id

        res = engine.settle_invoice_with_evidence(inv_id, evidence_dir)
        print("=" * 60)
        print(f"MPP SETTLEMENT VERDICT: {res['status']}")
        print("=" * 60)
        print(f"Invoice ID  : {res.get('invoice_id')}")
        print(f"Oracle Tier : {res.get('tier')}")
        print(f"Integrity   : {res.get('integrity_verdict')}")
        if "release_tx" in res:
            print(f"Release Tx  : {res.get('release_tx')}")
            print(f"Recipient   : {res.get('payout_recipient')} ({res.get('amount_usdc')} USDC)")
        elif "refund_tx" in res:
            print(f"Refund Tx   : {res.get('refund_tx')}")
            print(f"Dispute     : {res.get('dispute_reason')}")
        print("=" * 60)
        return 0 if res["status"] == "SETTLED_RELEASED" else 1

    else:
        print(f"unknown mpp subcommand: {subcmd!r}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tattva", description=f"TattvaSwarm {__version__} — sovereign personal AI swarm")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_doctor = sub.add_parser("doctor", help="env + backend health check")
    p_doctor.set_defaults(func=cmd_doctor)

    p_route = sub.add_parser("route", help="route one prompt through the tiered router")
    p_route.add_argument("prompt")
    p_route.add_argument("--tier", choices=("auto", *EXTENDED_TIERS), default="auto")
    p_route.add_argument("--provider", choices=("auto", "nebius", "muse"), default="auto")
    p_route.set_defaults(func=cmd_route)

    p_muse = sub.add_parser("muse", help="Shiva-Muse verifiable router, pipeline, and session bridge")
    muse_sub = p_muse.add_subparsers(dest="muse_cmd", required=True)

    m_route = muse_sub.add_parser("route", help="route prompt via ShivaMuseRouter")
    m_route.add_argument("prompt")
    m_route.add_argument("--modality", default="reasoning")
    m_route.add_argument("--task-id", type=int, default=0)
    m_route.add_argument("--live", action="store_true")

    m_pipe = muse_sub.add_parser("pipeline", help="run 8-stage Shiva-Muse verification pipeline")
    m_pipe.add_argument("prompt")
    m_pipe.add_argument("--task-type", default="reasoning")
    m_pipe.add_argument("--agent-id", type=int, default=0)
    m_pipe.add_argument("--live", action="store_true")

    m_resume = muse_sub.add_parser("resume", help="resume Meta Muse CLI UUIDv7 session")
    m_resume.add_argument("session_id", nargs="?", default="01a1c1c5-0154-7250-8767-f4beaff19eae")
    m_resume.add_argument("--prompt", default=None)
    m_resume.add_argument("--live", action="store_true")

    m_dream = muse_sub.add_parser("dream", help="manifest verified candidates via Wonder Dream")
    m_dream.add_argument("question")
    m_dream.add_argument("--candidates", type=int, default=4)

    m_gate = muse_sub.add_parser("gate", help="evaluate trace JSON with Ashta-Gate")
    m_gate.add_argument("trace_json")
    p_muse.set_defaults(func=cmd_muse)

    p_resume = sub.add_parser("resume", help="resume Meta Muse CLI UUIDv7 session directly")
    p_resume.add_argument("session_id", nargs="?", default="01a1c1c5-0154-7250-8767-f4beaff19eae")
    p_resume.add_argument("--prompt", default=None)
    p_resume.add_argument("--live", action="store_true")
    p_resume.set_defaults(func=cmd_muse, muse_cmd="resume")

    p_mem = sub.add_parser("memory", help="local persistent memory")
    mem_sub = p_mem.add_subparsers(dest="mem_cmd", required=True)
    m_add = mem_sub.add_parser("add")
    m_add.add_argument("text", nargs="+")
    m_add.add_argument("--kind", default="note")
    m_add.add_argument("--tags", nargs="*", default=None)
    m_search = mem_sub.add_parser("search")
    m_search.add_argument("query", nargs="+")
    m_search.add_argument("--limit", type=int, default=5)
    m_recent = mem_sub.add_parser("recent")
    m_recent.add_argument("--limit", type=int, default=10)
    mem_sub.add_parser("count")
    p_mem.set_defaults(func=cmd_memory)

    p_swarm = sub.add_parser("swarm", help="run a task graph (parallel -> verify -> synthesize)")
    swarm_sub = p_swarm.add_subparsers(dest="swarm_cmd", required=True)
    s_run = swarm_sub.add_parser("run")
    s_run.add_argument("spec", help="path to a tasks.json spec")
    p_swarm.set_defaults(func=cmd_swarm)

    p_code = sub.add_parser("code", help="run code in the hardened sandbox (code engine)")
    code_sub = p_code.add_subparsers(dest="code_cmd", required=True)
    c_run = code_sub.add_parser("run")
    c_run.add_argument("cmd", help="shell command to run inside the sandbox")
    c_run.add_argument("--image", default=None, help="container image (default python:3.12-slim)")
    c_run.add_argument("--timeout", type=float, default=30.0, help="wall-clock seconds")
    c_run.add_argument("--allow-network", action="store_true", help="enable network (off by default)")
    c_run.add_argument("--workdir", default=None, help="host dir mounted at /work")
    c_run.add_argument("--json", action="store_true")
    p_code.set_defaults(func=cmd_code)

    p_mcp = sub.add_parser("mcp", help="serve MCP tools over stdio (wait for a client)")
    p_mcp.set_defaults(func=cmd_mcp)

    # Frontier commands
    p_frontier = sub.add_parser("frontier", help="Frontier domain physical oracles and agent harness")
    frontier_sub = p_frontier.add_subparsers(dest="frontier_cmd", required=True)

    f_harness = frontier_sub.add_parser("harness", help="run agent harness (generates -> qualifies -> seals)")
    f_harness.add_argument("--task", default="tps", help="scramjet, tps, lunar_power, rubisco, backtranslate, or all")
    f_harness.add_argument("--evidence-dir", default="data/evidence/cli_run", help="evidence output directory")
    f_harness.add_argument("--agent", choices=["default", "tattva"], default="tattva", help="agent generator")

    f_verify = frontier_sub.add_parser("verify", help="verify sealed evidence directory")
    f_verify.add_argument("evidence_dir", help="path to evidence directory")

    f_adver = frontier_sub.add_parser("adversarial", help="run deterministic adversarial veto pack")
    f_adver.add_argument("--task", default=None, help="optional specific task to test")

    f_tree = frontier_sub.add_parser("treeseract", help="run Treeseract Q_n tree search with domain oracle pruning")
    f_tree.add_argument("--task", default="tps", help="scramjet, tps, lunar_power, rubisco, backtranslate")
    f_tree.add_argument("--dimension", type=int, default=4, help="hypercube Q_n dimension (default: 4)")
    f_tree.add_argument("--depth", type=int, default=2, help="search tree depth (default: 2)")
    f_tree.add_argument("--branch-factor", type=int, default=3, help="branching factor per node (default: 3)")
    f_tree.add_argument("--evidence-dir", default=None, help="optional evidence output directory")
    p_frontier.set_defaults(func=cmd_frontier)

    # Top-level treeseract alias
    p_tree_top = sub.add_parser("treeseract", help="run Treeseract Q_n tree search with domain oracle pruning")
    p_tree_top_sub = p_tree_top.add_subparsers(dest="tree_subcmd", required=True)
    t_run = p_tree_top_sub.add_parser("run", help="execute Treeseract search")
    t_run.add_argument("--task", default="tps", help="scramjet, tps, lunar_power, rubisco, backtranslate")
    t_run.add_argument("--dimension", type=int, default=4, help="hypercube Q_n dimension (default: 4)")
    t_run.add_argument("--depth", type=int, default=2, help="search tree depth (default: 2)")
    t_run.add_argument("--branch-factor", type=int, default=3, help="branching factor per node (default: 3)")
    t_run.add_argument("--evidence-dir", default=None, help="optional evidence output directory")
    p_tree_top.set_defaults(func=lambda a: cmd_frontier(argparse.Namespace(frontier_cmd="treeseract", **vars(a))))

    # Colab commands
    p_colab = sub.add_parser("colab", help="Google Colab bridge and connection utilities")
    colab_sub = p_colab.add_subparsers(dest="colab_cmd", required=True)

    c_status = colab_sub.add_parser("status", help="check status of local Colab bridge port")
    c_status.add_argument("--port", type=int, default=9223, help="bridge port (default: 9223)")

    colab_sub.add_parser("cell", help="output ready-to-paste Google Colab quickstart cell")
    p_colab.set_defaults(func=cmd_colab)

    # CDP commands (Coinbase Developer Platform / Base Agent Wallet)
    p_cdp = sub.add_parser("cdp", help="Coinbase Developer Platform & Base Agent Wallet utilities")
    cdp_sub = p_cdp.add_subparsers(dest="cdp_cmd", required=True)

    cdp_w = cdp_sub.add_parser("wallet", help="show or generate sovereign agent wallet")
    cdp_w.add_argument("--network", default="base-mainnet", choices=["base-mainnet", "base-sepolia"])

    cdp_b = cdp_sub.add_parser("balance", help="check ETH and USDC balance on Base")
    cdp_b.add_argument("--address", default=None, help="wallet address (default: local agent wallet)")
    cdp_b.add_argument("--network", default="base-mainnet", choices=["base-mainnet", "base-sepolia"])

    cdp_f = cdp_sub.add_parser("faucet", help="request testnet drip on Base Sepolia")
    cdp_f.add_argument("--address", default=None, help="wallet address (default: local agent wallet)")

    cdp_p = cdp_sub.add_parser("pay", help="execute x402 payment challenge")
    cdp_p.add_argument("--challenge-id", required=True, help="challenge ID (c_...)")
    cdp_p.add_argument("--amount", type=float, default=0.05, help="USDC amount")
    cdp_p.add_argument("--recipient", default="0xDeliciosoRadhaTreasury", help="recipient address")
    p_cdp.set_defaults(func=cmd_cdp)

    # MPP commands (Machine Payment Protocol for A2A settlement)
    p_mpp = sub.add_parser("mpp", help="Machine Payment Protocol for autonomous A2A settlement")
    mpp_sub = p_mpp.add_subparsers(dest="mpp_cmd", required=True)

    mpp_inv = mpp_sub.add_parser("invoice", help="create A2A escrow invoice for subagent task")
    mpp_inv.add_argument("--delegator", default="Agent-Orchestrator-01", help="delegator agent ID")
    mpp_inv.add_argument("--worker", default="Agent-Oracle-Worker", help="worker agent ID")
    mpp_inv.add_argument("--task", default="tps", help="task name")
    mpp_inv.add_argument("--bounty", type=float, default=0.05, help="bounty in USDC")

    mpp_set = mpp_sub.add_parser("settle", help="settle escrow against DharmaGate sealed evidence")
    mpp_set.add_argument("--invoice-id", required=True, help="invoice ID (mpp_...)")
    mpp_set.add_argument("--evidence-dir", default="data/evidence/treeseract_tps", help="sealed evidence directory")
    p_mpp.set_defaults(func=cmd_mpp)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
