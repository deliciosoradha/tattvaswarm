#!/usr/bin/env python3
"""A short sovereign-assistant session: recall -> route -> reply -> remember.

Everything is local except the chosen model call (Nebius Token Factory).
Usage:  python3 demos/demo_assistant.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tattva_swarm.memory import Memory  # noqa: E402
from tattva_swarm.router import route  # noqa: E402

QUESTIONS = [
    ("normal", "In one sentence: what is a personal AI assistant?"),
    ("small", "hola"),
]


def main() -> int:
    mem = Memory()
    print(f"memory entries before: {mem.count()}")
    for hit in mem.search("assistant", limit=3):
        print(f"  recall: {hit['text'][:100]}")

    for tier, question in QUESTIONS:
        out = route(question, tier=tier)
        print(f"\nQ [{tier}] {question}")
        print(f"A {str(out.get('reply'))[:300]}")
        print(f"  model={out.get('model')} latency={out.get('latency_s')}s usage={out.get('usage')}")
        if out.get("status") == "ok":
            mem.add(
                f"Q: {question}\nA: {str(out.get('reply'))[:500]}",
                kind="assistant-log",
                source=str(out.get("model") or "small-local"),
            )

    print(f"\nmemory entries after: {mem.count()}  ({mem.path})")
    mem.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
