# Recursive Self-Improvement — the Learning Gate (sovereign edition)

Status: gate + emission **IMPLEMENTED / VERIFIED** (`src/tattva_swarm/learning_gate.py`,
`tests/test_learning_gate.py`). Automated retrain trigger and promotion gate:
**PLANNED** (ties into `hermes cron` scheduling and the LoRA post-training pipeline).

The invariant (operator directive, 2026-10-19): the system only trains on what
it **learned** — never on noise, never on what it already knew, and never at the
cost of privacy. Training is **private and dedicated to each identity** (a
person, a company, a project); nothing is shared, nothing syncs.

## The loop

```
 interaction ──► episode recorded (question, attempts, resolution)
                     │                        [private: $TATTVA_HOME/private/<identity>/]
                     ▼
              LEARNING GATE  ── skip: no_learning_event / duplicate / secret / …
                     │ pass
                     ▼
        supervised chat pairs (router_sft schema)  ──► LoRA post-training
                     │                                      (private adapter)
                     ▼
        promote only if the regression suite improves  ── PLANNED (see below)
```

Only episodes where the system **failed first and then resolved** become
training pairs. "Under the LoRA principle" the surface is very broad — so the
gate emits **supervised** pairs only, and the training stays closed per identity.

## Gate criteria (all must hold to emit a pair)

| Check | Rule | Skipped reason |
|---|---|---|
| Shape | question + resolution present | `missing_fields` |
| Substance | resolution ≥ 24 chars | `resolution_too_short` |
| **Learning event** | ≥ 1 failed attempt, or `initially_unresolved` | `no_learning_event` |
| Truthfulness | resolution is not an echo of the question | `trivial_echo` |
| Privacy | no key/token-looking content (`sk-…`, long hex/base64 blobs) | `possible_secret` |
| Bounds | question ≤ 4000 chars | `question_too_long` |
| Novelty | Jaccard(question) < 0.85 vs emitted + accepted candidates | `duplicate_question` |
| Anti-saturation | ≤ `max_pairs_per_day` (default 200) | `daily_cap_reached` |

Episodes are idempotent by question: recording an unresolved episode first and
the resolution later **completes it in place** (no duplicates, no silent no-ops).

## Emitted pairs

Exactly the schema the router post-training already consumes — so the same
pipeline and merge recipes apply unchanged:

```json
{"messages": [
  {"role": "system", "content": "You are a private personal assistant …"},
  {"role": "user", "content": "<question>"},
  {"role": "assistant", "content": "<verified resolution>"}],
 "episode_id": "…", "identity": "…", "ts": …, "source": "learning-gate/v1"}
```

## Privacy model

- Everything lives under `$TATTVA_HOME/private/<identity>/` (dir `0700`, files `0600`).
- Identity is the tenant boundary: a user, a company or a project. Two
  identities never see each other's episodes or pairs (tested).
- Nothing leaves the machine by default. When a private fine-tune is
  explicitly requested, only the curated pairs travel (to Token Factory), and
  the resulting adapter stays tied to that identity.
- Related legal notes (Token Factory legal quick guide, 2026-10-19): fine-tune
  data is processed in the EU; you own your fine-tuned models; Zero Data
  Retention is available for sensitive workloads. This local-first design keeps
  raw episodes on-host regardless.

## CLI

```bash
python3 -m tattva_swarm.learning_gate record --identity acme --json '<episode>'
python3 -m tattva_swarm.learning_gate gate   --identity acme    # dry run
python3 -m tattva_swarm.learning_gate emit   --identity acme    # append pairs
python3 -m tattva_swarm.learning_gate status --identity acme
```

## Recursion policy (PLANNED wiring)

1. Cron (`hermes cron`) runs `emit` per identity on a cadence (daily).
2. When a batch ≥ N pairs accumulates, schedule a private LoRA job.
3. Promotion gate: run the regression suite (router tier accuracy + held-out
   val split + the identity's own history) against the new adapter **merged**
   with the current one (`training/merge_lora_light.py`,
   `training/fuse_loras.py`); promote only on improvement, otherwise keep the
   previous adapter.
4. Everything logged per identity for audit; the gate's skip reasons are the
   training ledger.
