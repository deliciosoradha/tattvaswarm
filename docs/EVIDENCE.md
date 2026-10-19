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

## 5. Rust core (`tattva-engine`) — parity and hardening (2026-10-19)

The Rust core (`engine/`, std-only, built offline with `cargo build --release`)
reproduces the reference engine bit-for-bit and sandboxes commands in Docker:

| Check | Result |
|---|---|
| `run-swarm --workers 100000 --steps 6 --seed 7` | solves **6,063**, checksum `45f348f1ab454d00` — identical to Python |
| Same run, wall time | **0.0303 s** vs 4.2498 s in Python (~140×) |
| `run-swarm --workers 1000000` | checksum `cc269c30bdd7654b` — identical to Python; **0.2324 s** vs 39.2885 s (~169×) |
| `exec --cmd 'echo … && head -1 /etc/os-release'` | exit 0, image `python:3.12-slim`, **no network**, 4.8 s |
| `exec --cmd 'sleep 30' --timeout 3` | exit 124, `timed_out: true`, 3.7 s (hard kill) |

Determinism is preserved across implementations: identical configuration →
identical checksum, on both engines.

## 6. LangChain adapter — live smoke (2026-10-19)

`ChatTattvaSwarm` (optional extra, `langchain-core` only) issued a real call to
the tiered router on Nebius Token Factory:

- Prompt: *"Reply with exactly three words: tattva langchain verified"*
- Reply: `tattva langchain verified` · model `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` · 148 tokens · tier `normal`

Backend failures raise instead of fabricating answers (test-asserted).

## Honesty notes

- The pure-Python reference is ~4 orders of magnitude slower than the GPU
  variant — that is expected and stated. The benchmarks above are the only
  performance claims made anywhere in this repository.
- Test host: 4 cores, ~6.7 GB RAM, no GPU (2026-10-19).
