#!/usr/bin/env python3
"""Run the swarm conductor on a task graph: parallel -> verify -> synthesize.

Usage:  python3 demos/demo_swarm_research.py [tasks.json]
Default spec: demos/tasks_research.example.json
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from tattva_swarm.conductor import run_graph  # noqa: E402


def main() -> int:
    spec_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (REPO / "demos" / "tasks_research.example.json")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    print(f"TattvaSwarm conductor — spec: {spec_path.name}")
    print(f"goal: {spec.get('goal', '')}\n")

    out = run_graph(spec)

    for r in out["results"]:
        reply = str(r.get("reply", ""))[:220].replace("\n", " ")
        print(f"[{r.get('id')}] tier={r.get('tier')} status={r.get('status')} model={r.get('model')}")
        print(f"    {reply}{'…' if len(str(r.get('reply', ''))) > 220 else ''}")

    if out.get("verifications"):
        print("\nverifications:")
        for v in out["verifications"]:
            print(f"  [{v.get('id')}] {v.get('verdict')} {str(v.get('detail', v.get('reason', '')))[:140]}")

    synth = out.get("synthesis") or {}
    print(f"\nsynthesis: status={synth.get('status')} model={synth.get('model')}")
    if synth.get("status") == "ok":
        print(str(synth.get("reply", ""))[:1200])

    print(f"\nusage_total_tokens: {out.get('usage_total_tokens')}")
    ok = all(r.get("status") == "ok" for r in out.get("results", [])) and synth.get("status") == "ok"
    return 0 if ok else 3


if __name__ == "__main__":
    raise SystemExit(main())
