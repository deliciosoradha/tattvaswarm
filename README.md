# TattvaSwarm — a sovereign personal AI swarm

> **Status (Oct 2026):** active build for the [Nebius × NVIDIA Global AI Hackathon](https://nebiusglobalaihackathon.devpost.com/rules).
> Sections below marked *(in progress)* are being implemented during the hackathon window; everything
> else reflects working code or measured evidence. Honest states only — nothing here is aspirational fiction.

TattvaSwarm is an always-on, **local-first personal AI system** that coordinates a swarm of
*logical* workers with persistent memory, reusable skills, and tiered access to **NVIDIA Nemotron
models on Nebius Token Factory**. Your memory, tasks and credentials live on your machine; only the
inference calls you allow leave it.

## What it does

- **Tiered routing** *(in progress)* — `small` → local determinism, `normal` → Nemotron Nano,
  `reasoning` → Nemotron Super, `research` → external tools. No backend? Honest `503` with the
  exact reason — it never invents an answer.
- **Logical worker swarms** *(in progress)* — N logical agents executed compactly in a single
  process (no N processes). Measured evidence so far: **54,000,000 logical agents in 2.8671 s**
  (Colab T4) and **108,000,000 in 5.8007 s** (A100 40 GB).
- **Persistent memory** *(in progress)* — a local SQLite + FTS fabric of decisions, notes and
  results, recalled across sessions.
- **Kanban-style conductor** *(in progress)* — parallel workers → verifier → synthesizer, tracked
  as a task graph.
- **Sovereignty by design** — a documented data policy (`docs/SOVEREIGNTY.md`): what leaves the
  machine is an explicit allowlist of model calls; everything else stays local.

## Quickstart

*(final commands land as modules are implemented — H-006 → H-010 in the project board)*

```bash
git clone <this-repo> && cd tattva-swarm
python -m venv .venv && . .venv/bin/activate
pip install -e .

cp .env.example .env          # then set NEBIUS_API_KEY (https://tokenfactory.nebius.com/)

python scripts/smoke_token_factory.py --list-models   # confirm available Nemotron models
tattva doctor                                          # check env + backend reachability
```

## Why Nebius Token Factory + NVIDIA models

All LLM reasoning goes through Token Factory's OpenAI-compatible API with NVIDIA open-source
models (Nemotron 3 family), mapped to routing tiers — fast everyday calls on Nano, serious
reasoning on Super. Details and exact model IDs: `docs/TOKEN_FACTORY.md`.

## Data sovereignty

TattvaSwarm stores everything locally (`~/.tattva` by default): memory, task graph, run logs and a
per-call usage ledger. The repository ships **synthetic examples only** — no personal data, no
secrets. See `docs/SOVEREIGNTY.md`.

## License

Apache-2.0 — see `LICENSE`.
