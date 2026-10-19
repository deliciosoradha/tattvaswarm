# Hackathon notes — Nebius × NVIDIA Global AI Hackathon 2026

> Submission window: 2026-08-26 → 2026-10-30 10:00 PT. This document is part of
> the submission package and follows the rule that any pre-existing project
> must explain **how it was significantly updated during the Submission Period**.

## Track

**Primary: Personal AI** — an always-on, private assistant with persistent
memory, reusable skills and data that stays under the user's control, built
with tools including **Hermes Agent** and powered by NVIDIA open models on
Nebius Token Factory.

*Alternate (decision held until ≤ 2026-10-25, once the live demo is up):*
**Best Apps and Agents**. The build serves both tracks; the final choice is
recorded in the submission form.

## How this project uses Nebius + NVIDIA (rules requirement)

- **Runtime calls to Nebius Token Factory** — every `normal` / `reasoning` /
  `heavy` routed call goes to `https://api.tokenfactory.nebius.com/v1/`
  (OpenAI-compatible). See `docs/TOKEN_FACTORY.md` for the verified catalog.
- **NVIDIA open-source models** — Nemotron 3 family, mapped to tiers:
  Nano-30B-A3B (fast), Super-120B-a12b (reasoning), Ultra-550B-a55b (heavy).
  All three verified live (`docs/EVIDENCE.md`, §3).

## What was updated during the Submission Period (2026-10-19 → ...)

Everything **in this repository** is new work created inside the submission
window. The underlying control-plane experiments (local prompt router, logical
swarm benchmarks, fabric-style memory experiments) predate it; the following
is what changed or was created *during* the window:

1. **Nebius Token Factory integration** — new `nebius.py` client (stdlib-only),
   tier map, usage ledger, honest-degradation semantics; live smoke evidence.
2. **Public reference engine** — `engine.py`: logical workers as deterministic,
   checksummed state machines (scaled benchmarks documented in `EVIDENCE.md`).
3. **Sovereign memory** — `memory.py`: local SQLite+FTS persistent memory.
4. **Conductor** — `conductor.py`: parallel workers → verifier → synthesizer,
   demonstrated end-to-end on live Nemotron models (2.3–2.6k tokens/run).
5. **CLI + demo app** — `tattva doctor/route/memory/swarm`; live web demo.
6. **Documentation** — architecture, sovereignty policy, evidence, this file —
   all written during the window; repository published as open source
   (Apache-2.0) for the first time.

## Status honesty

- Working: router tiers (small/normal/reasoning/heavy), Token Factory calls,
  memory, conductor, CLI, demos, live demo deployment (see README links).
- Not run / not claimed: `research` tier (needs a Tavily key — honest error),
  vision tier (Super-VL evaluated for optional demos only).
- Every performance number in this repo is a measured number with date and
  conditions — see `docs/EVIDENCE.md`.
