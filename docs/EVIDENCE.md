# Evidence — measured numbers only

Everything on this page was measured by the project authors. Nothing is
estimated, extrapolated, or copied from marketing. Dates and conditions are
included so you can judge them.

## 1. Logical swarm engine — scaled engine, GPU (2026-10-18)

The scaled engine (Rust/CUDA variant) was benchmarked on two rented GPUs:

| Run | GPU | Logical agents | Wall time | Throughput | Result |
|---|---|---|---|---|---|
| `stage-b-colab-t4` | Tesla T4 | 54,000,000 | 2.8671 s | ~18.8 M agents/s | 19 cohorts, 0 conflicts |
| `dolphin-evo-2026-10-18` | A100-SXM4-40GB | 108,000,000 | 5.8007 s | ~18.6 M solves/s | residual 0 |

Key point: these are **logical** workers — state machines advanced in compact
kernels — not processes. That is why millions per second fit on one GPU.

## 2. Reference engine — pure Python, this repository (2026-10-19)

The dependency-free reference implementation (`src/tattva_swarm/engine.py`) is
intentionally modest. Measured on a low-power 4-core host:

| Scale | Wall time | Solves | Solves/s | Checksum (verifiable) |
|---|---|---|---|---|
| 100,000 logical workers, 6 steps | 4.2498 s | 6,063 | 1,426.7 | `45f348f1ab454d00` |
| 1,000,000 logical workers, 6 steps | 39.2885 s | 60,299 | 1,534.8 | `cc269c30bdd7654b` |

Fully deterministic: identical configuration → identical checksum.

Reproduce: `python3 demos/demo_mass_swarm.py`

## 3. Nebius Token Factory — smoke evidence (2026-10-19)

| Check | Result |
|---|---|
| `GET /v1/models` | HTTP 200 · 28 models · 5 NVIDIA/Nemotron |
| Nano-30B chat | HTTP 200 · `TATTVA_OK` · 2.864 s (61 completion tokens) |
| Super-120B chat | HTTP 200 · coherent answer · 1.943 s (77 completion tokens, 44 reasoning) |
| Ultra-550B chat | HTTP 200 · coherent answer · 1.561 s (43 completion tokens) |

Raw evidence JSON: `reports/nebius-hack-2026/smoke_*_20261019.json` (local lab).

## 4. End-to-end conductor run (2026-10-19)

`python3 demos/demo_swarm_research.py` — 3 parallel workers (Nano + Super),
3 verifications, 1 synthesis (Ultra-550B):

- all 3 workers `status=ok`
- all 3 verifications `VERIFIED`
- synthesis `status=ok` (Ultra-550B), usage total **2,334 tokens**
- CLI path (`tattva swarm run`) re-run: **2,566 tokens**, same verdicts

## Honesty notes

- The pure-Python reference is ~4 orders of magnitude slower than the GPU
  variant — that is expected and stated. The benchmarks above are the only
  performance claims made anywhere in this repository.
- Test host: 4 cores, ~6.7 GB RAM, no GPU (2026-10-19).
