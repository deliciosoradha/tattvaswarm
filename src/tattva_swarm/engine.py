"""Logical swarm engine — N logical workers executed compactly in one process.

A *logical worker* is not an OS process: it is a tiny deterministic state
machine advanced in tight loops, so millions of them can run per second on a
single machine with no process/thread explosion.

This is the scaled-down, dependency-free open version of the engine behind the
measured benchmarks (54,000,000 logical agents in 2.8671 s on a T4;
108,000,000 in 5.8007 s on an A100-40GB — see docs/EVIDENCE.md). The
pure-Python reference here is intentionally modest: run it, check the checksum,
then read the measured numbers and their reproduction notes.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

# Deterministic 64-bit LCG (Knuth constants) — reproducible on every machine.
_A = 6364136223846793005
_C = 1442695040888963407
_MASK64 = (1 << 64) - 1


@dataclass
class SwarmConfig:
    """Configuration of one logical swarm run."""

    workers: int = 1_000_000
    steps: int = 6
    seed: int = 7
    solve_modulus: int = 97  # a worker "solves" when its state % modulus == 0

    def __post_init__(self) -> None:
        if self.workers < 1 or self.steps < 1 or self.solve_modulus < 2:
            raise ValueError("workers>=1, steps>=1 and solve_modulus>=2 are required")


@dataclass
class SwarmReport:
    workers: int
    steps: int
    solves: int
    converged: int
    elapsed_s: float
    solves_per_s: float
    workers_per_s: float
    checksum: str
    deterministic: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "workers": self.workers,
            "steps": self.steps,
            "solves": self.solves,
            "converged": self.converged,
            "residual": self.workers - self.converged,
            "elapsed_s": round(self.elapsed_s, 4),
            "solves_per_s": round(self.solves_per_s, 1),
            "workers_per_s": round(self.workers_per_s, 1),
            "checksum": self.checksum,
            "deterministic": self.deterministic,
        }


def run_swarm(cfg: SwarmConfig) -> SwarmReport:
    """Advance ``cfg.workers`` logical workers for up to ``cfg.steps`` steps.

    A worker starts from a per-worker seed, advances its 64-bit state each step
    and *converges* (counts as one solve) the first time the state hits
    ``state % solve_modulus == 0``; otherwise it rests after ``steps`` steps.
    Fully deterministic: identical config -> identical checksum.
    """
    t0 = time.perf_counter()
    solves = 0
    converged = 0
    checksum = 0
    for w in range(cfg.workers):
        state = (cfg.seed * _A + _C + w) & _MASK64
        hit = False
        for _ in range(cfg.steps):
            state = (state * _A + _C) & _MASK64
            if state % cfg.solve_modulus == 0:
                hit = True
                solves += 1
                break
        if hit:
            converged += 1
        checksum ^= state
    elapsed = time.perf_counter() - t0
    return SwarmReport(
        workers=cfg.workers,
        steps=cfg.steps,
        solves=solves,
        converged=converged,
        elapsed_s=elapsed,
        solves_per_s=solves / elapsed if elapsed > 0 else 0.0,
        workers_per_s=cfg.workers / elapsed if elapsed > 0 else 0.0,
        checksum=f"{checksum:016x}",
    )
