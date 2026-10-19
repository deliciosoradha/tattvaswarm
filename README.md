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
- **Rust core, bit-identical** — the same engine as a std-only Rust binary: identical checksums,
  ~140–170× faster (100k workers in 0.030 s, 1M in 0.232 s — measured,
  [`docs/EVIDENCE.md`](docs/EVIDENCE.md) §5).
- **Code engine with a hardened sandbox** — agent-authored commands run in a container with no
  network by default, memory/CPU/pids caps and a wall-clock watchdog; code never executes on the
  host ([`docs/SANDBOX.md`](docs/SANDBOX.md)).
- **Persistent sovereign memory** — SQLite + FTS5 on your disk; nothing syncs anywhere, because
  there is nowhere to sync to.
- **Conductor** — parallel workers → verifier pass → heavy-model synthesis: one full demo run
  costs ~2.3–2.6k tokens end-to-end (measured).
- **Agent surfaces** — the same capabilities as an **MCP server** (stdio, 6 tools) and a
  **LangChain** adapter (`ChatTattvaSwarm` + tools), so any agent framework can drive the swarm
  ([`docs/MCP.md`](docs/MCP.md), [`docs/LANGCHAIN.md`](docs/LANGCHAIN.md)).
- **Sovereignty by policy** — an explicit allowlist of what may leave the machine, a local usage
  ledger for every outbound call, and a pre-push sanitization scanner
  ([`docs/SOVEREIGNTY.md`](docs/SOVEREIGNTY.md)).

## Quickstart (tested)

```bash
git clone https://github.com/deliciosoradha/tattvaswarm.git && cd tattvaswarm

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

### Rust core + code engine (optional, recommended)

```bash
bash engine/build.sh                  # std-only Rust core, ~4 min on 4 cores
PYTHONPATH=src python3 -m tattva_swarm.sandbox --cmd 'echo hello from the sandbox' --json
```

### MCP server (stdio)

```bash
PYTHONPATH=src python3 -m tattva_swarm.mcp_server   # 6 tools for any MCP client
```

### Demos

```bash
python3 demos/demo_assistant.py       # recall → route → reply → remember
python3 demos/demo_swarm_research.py  # 3 parallel workers → verifier → Ultra synthesis
python3 demos/demo_mass_swarm.py      # logical swarm engine: 100k → 1M workers
```

### Live demo

**`«demo URL»`** — the same router behind a tiny stdlib web app, deploying to **Nebius AI
Cloud** as a CPU serverless endpoint (one command: [`deploy_nebius.sh`](deploy_nebius.sh));
HF Space fallback prepared in [`spaces/`](spaces/) (`deploy_hf.sh`). Rate-limited either way.

## Post-training on Token Factory

The router ships with a 200-example, parity-verified SFT dataset generated from its own
classifier, and two LoRA fine-tuning jobs on **Nebius Token Factory** (`Qwen/Qwen3-0.6B` and
`unsloth/gpt-oss-20b-BF16`). Merging the adapters is dependency-light on purpose: a zero-torch
merger ([`training/merge_lora_light.py`](training/merge_lora_light.py), numpy only) plus the
official recipe ([`training/merge_lora_torch.py`](training/merge_lora_torch.py)). Job IDs,
statuses and merge evidence: [`docs/POST_TRAINING.md`](docs/POST_TRAINING.md).

## Docs

| Doc | What's in it |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | components, data flow, concurrency model |
| [`docs/TOKEN_FACTORY.md`](docs/TOKEN_FACTORY.md) | verified model catalog, tier map, measured latencies |
| [`docs/SANDBOX.md`](docs/SANDBOX.md) | code engine: hardened sandbox, verified runs, cloud-swap path |
| [`docs/SANDBOXES.md`](docs/SANDBOXES.md) | Nebius Sandboxes (Contree): CLI (uv), auth, quickstart, cookbook |
| [`docs/MCP.md`](docs/MCP.md) | MCP server: 6 tools over stdio + client config |
| [`docs/LANGCHAIN.md`](docs/LANGCHAIN.md) | LangChain adapter: chat model + tools |
| [`docs/POST_TRAINING.md`](docs/POST_TRAINING.md) | router post-training: dataset, jobs, merge, endpoint |
| [`docs/LORA_FUSION.md`](docs/LORA_FUSION.md) | fusing accumulated LoRAs into one adapter (zero-torch) |
| [`docs/SELF_IMPROVEMENT.md`](docs/SELF_IMPROVEMENT.md) | the learning gate: private, per-identity self-improvement |
| [`docs/SOVEREIGNTY.md`](docs/SOVEREIGNTY.md) | what leaves your machine (allowlist) and what never does |
| [`docs/EVIDENCE.md`](docs/EVIDENCE.md) | every measured number, with conditions + reproduction |
| [`docs/HACKATHON.md`](docs/HACKATHON.md) | track + exactly what was updated in the submission window |
| [`docs/VIDEO_SCRIPT.md`](docs/VIDEO_SCRIPT.md) | <3-minute demo script + EN subtitles |
| [`docs/SUBMISSION.md`](docs/SUBMISSION.md) | Devpost form draft + Nebius feedback |

## Verify it yourself

```bash
python3 -m pytest -q tests/                            # 50 offline tests, 2 skipped — no key needed
bash scripts/sanitize_check.sh                         # pre-push secrets/PII scan → CLEAN
python3 scripts/smoke_token_factory.py --list-models   # live catalog check
```

## Data sovereignty

Memory, ledger and logs live in `~/.tattva` (or `$TATTVA_HOME`). The repository ships
**synthetic examples only** — no personal data, no secrets. Your key never needs to live in the
repository: `$TATTVA_HOME/nebius.env` is read automatically.

## License

Apache-2.0 — see [`LICENSE`](LICENSE).
