#!/usr/bin/env python3
"""Run a compact logical swarm on this machine and print the measured report.

Usage:  python3 demos/demo_mass_swarm.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tattva_swarm.engine import SwarmConfig, run_swarm  # noqa: E402


def main() -> int:
    scales = [(100_000, 6), (1_000_000, 6)]
    print("TattvaSwarm — logical swarm demo (pure-Python reference engine)\n")
    for workers, steps in scales:
        report = run_swarm(SwarmConfig(workers=workers, steps=steps))
        payload = {"scale": f"{workers:,} logical workers", **report.to_dict()}
        print(json.dumps(payload, indent=2))
        print()
    print("Measured GPU benchmarks of the scaled engine: docs/EVIDENCE.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
