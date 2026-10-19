# Architecture

```
                 ┌────────────────────────────────────────────────────────┐
 user / CLI ───▶ │  router.classify(prompt)  →  deterministic tier choice │
 (tattva ...)    └───────────────┬────────────────────────────────────────┘
                                 │
        ┌────────────┬───────────┼────────────────┬─────────────────┐
        ▼            ▼           ▼                ▼                 ▼
   small        normal      reasoning          heavy           research
 (local, no   (Nemotron    (Nemotron       (Nemotron        (Tavily,
  LLM call)    Nano)        Super)          Ultra)           optional)
        │            │           │                │                 │
        └────────────┴─────┬─────┴────────────────┘                 │
                           ▼                                        │
                 nebius.TokenFactoryClient  ◀── OpenAI-compatible  │
                 (stdlib urllib, usage ledger)                      │
                           │                                        │
                           ▼                                        ▼
                 $TATTVA_HOME/usage.jsonl               structured error
                 (local, per-call)                      if not configured
```

## Components

| Module | Responsibility |
|---|---|
| `router.py` | tier contract: `small` / `normal` / `reasoning` / `heavy` / `research`; deterministic classification; honest degradation |
| `nebius.py` | Token Factory client (stdlib only), usage ledger, env loading (`repo/.env` → `$TATTVA_HOME/nebius.env`) |
| `memory.py` | persistent local memory, SQLite + FTS5, nothing leaves the machine |
| `engine.py` | logical swarm engine: N workers as compact state machines (deterministic, checksummed) |
| `conductor.py` | task graph: parallel workers → verifier (fast tier) → synthesizer (heavy tier) |
| `cli.py` | `tattva doctor / route / memory / swarm` |

## Data flow of one prompt

1. `route(prompt)` loads env and classifies → tier + reason.
2. `small` → answered locally. `research` → Tavily (or honest error).
3. Otherwise the tier's model id is resolved and one `chat/completions` call
   is made to Token Factory; usage is appended to the local ledger.
4. On any backend failure the call returns `{"status": "error", …}` with the
   exact reason — never a fabricated answer.

## Concurrency model

- The conductor runs workers in **threads** (I/O-bound LLM calls), capped by
  `max_workers` (default 3).
- The engine runs **logical** workers inside one process — no threads, no
  processes per agent. That is the scalability trick: state machines, not
  schedulers.

## Extending

- New tier: add a hint set in `router.classify`, a model id in `.env`, done.
- New backend: implement a `chat()`-shaped client and pass it to `route()`
  (tests do exactly this with a keyless stub).
