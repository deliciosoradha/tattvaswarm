"""TattvaSwarm CLI — `tattva <command>`.

Commands:
  tattva doctor                          env + backend health check (honest, never fakes OK)
  tattva route "prompt" [--tier T]       route one prompt through the tiered router
  tattva memory add|search|recent|count  local persistent memory
  tattva swarm run tasks.json            parallel -> verify -> synthesize (conductor)
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__
from .nebius import BackendError, TokenFactoryClient, load_env_file, tattva_home
from .router import TIERS, route, tier_models


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
    out = route(args.prompt, tier=args.tier)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if out.get("status") == "ok" else 3


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tattva", description=f"TattvaSwarm {__version__} — sovereign personal AI swarm")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_doctor = sub.add_parser("doctor", help="env + backend health check")
    p_doctor.set_defaults(func=cmd_doctor)

    p_route = sub.add_parser("route", help="route one prompt through the tiered router")
    p_route.add_argument("prompt")
    p_route.add_argument("--tier", choices=("auto", *TIERS), default="auto")
    p_route.set_defaults(func=cmd_route)

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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
