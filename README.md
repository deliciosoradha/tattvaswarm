# TattvaSwarm — a sovereign personal AI swarm

> **Status (Oct 2026):** built for the [Nebius × NVIDIA Global AI Hackathon](https://nebiusglobalaihackathon.devpost.com/rules).
> Every command below was run against live **Nebius Token Factory** with **NVIDIA Nemotron**
> models; the measured numbers and their conditions live in [`docs/EVIDENCE.md`](docs/EVIDENCE.md).
> Honest states only — nothing here is aspirational fiction.

TattvaSwarm is a **local-first personal AI system**: a deterministic tiered router, persistent
memory that physically stays on your machine, a parallel→verify→synthesize conductor, and a
logical swarm engine that runs millions of workers as compact state machines — not processes.
Only the inference calls you allow ever leave the machine, and every one of them is recorded in
a local ledger.

## What it does

- **Tiered routing** — `small` is answered locally and never touches the network; `normal` →
  Nemotron Nano, `reasoning` → Nemotron Super, `heavy` → Nemotron Ultra (all on Nebius Token
  Factory); `research` is optional Tavily search. A missing or misconfigured backend returns a
  structured error with the **exact reason** — it never invents an answer.
- **Evidence-backed swarm engine** — logical workers as deterministic, checksummed state
  machines: 100,000 workers in 4.25 s in pure Python on a 4-core host; the scaled engine measured
  **108,000,000 logical workers in 5.8007 s** on an A100-40GB (54,000,000 in 2.8671 s on a T4).
  Run it: `python3 demos/demo_mass_swarm.py`.
- **Persistent sovereign memory** — SQLite + FTS5 on your disk; nothing syncs anywhere, because
  there is nowhere to sync to.
- **Conductor** — parallel workers → verifier pass → heavy-model synthesis: one full demo run
  costs ~2.3–2.6k tokens end-to-end (measured).
- **Sovereignty by policy** — an explicit allowlist of what may leave the machine, a local usage
  ledger for every outbound call, and a pre-push sanitization scanner
  ([`docs/SOVEREIGNTY.md`](docs/SOVEREIGNTY.md)).

## Quickstart (tested)

```bash
git clone «repo URL» tattva-swarm && cd tattva-swarm

python3 -m venv .venv && . .venv/bin/activate   # Debian/Ubuntu: sudo apt install python3-venv
pip install -e .                                 # zero runtime dependencies

export NEBIUS_API_KEY=...   # https://tokenfactory.nebius.com/  (or: ~/.tattva/nebius.env)

tattva doctor                 # key present? tiers? backend reachable?
tattva route "Say hello in one short line."                              # → Nemotron Nano
tattva route "Analyze the trade-offs of local-first AI" --tier reasoning # → Nemotron Super
tattva memory add "The router prefers Nano for everyday calls" --kind note
tattva memory search Nano
```

Or run without installing — exactly the same code path:

```bash
PYTHONPATH=src python3 -m tattva_swarm.cli doctor
```

### Demos

```bash
python3 demos/demo_assistant.py       # recall → route → reply → remember
python3 demos/demo_swarm_research.py  # 3 parallel workers → verifier → Ultra synthesis
python3 demos/demo_mass_swarm.py      # logical swarm engine: 100k → 1M workers
```

### Live demo

**`«HF Space URL»`** — the same router behind a tiny stdlib web app
([`spaces/demo/`](spaces/demo/)), rate-limited; one-command deploy script:
[`spaces/deploy_hf.sh`](spaces/deploy_hf.sh).

## Docs

| Doc | What's in it |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | components, data flow, concurrency model |
| [`docs/TOKEN_FACTORY.md`](docs/TOKEN_FACTORY.md) | verified model catalog, tier map, measured latencies |
| [`docs/SOVEREIGNTY.md`](docs/SOVEREIGNTY.md) | what leaves your machine (allowlist) and what never does |
| [`docs/EVIDENCE.md`](docs/EVIDENCE.md) | every measured number, with conditions + reproduction |
| [`docs/HACKATHON.md`](docs/HACKATHON.md) | track + exactly what was updated in the submission window |
| [`docs/VIDEO_SCRIPT.md`](docs/VIDEO_SCRIPT.md) | <3-minute demo script + EN subtitles |
| [`docs/SUBMISSION.md`](docs/SUBMISSION.md) | Devpost form draft + Nebius feedback |

## Verify it yourself

```bash
python3 -m pytest -q tests/                            # 10 offline tests — no key needed
bash scripts/sanitize_check.sh                         # pre-push secrets/PII scan → CLEAN
python3 scripts/smoke_token_factory.py --list-models   # live catalog check
```

## Data sovereignty

Memory, ledger and logs live in `~/.tattva` (or `$TATTVA_HOME`). The repository ships
**synthetic examples only** — no personal data, no secrets. Your key never needs to live in the
repository: `$TATTVA_HOME/nebius.env` is read automatically.

## License

Apache-2.0 — see [`LICENSE`](LICENSE).
