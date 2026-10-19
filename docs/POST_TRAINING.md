# Post-training the router on Token Factory

The tier classifier is the one part of TattvaSwarm that benefits from fine-tuning: it
decides where every prompt goes. The heuristics generate the training data themselves,
which makes the dataset **reproducible and parity-verified** — every label is produced by
`classify()` and re-checked against it.

```bash
python3 training/gen_router_sft.py     # writes training/router_sft/{train,val}.jsonl
```

## Dataset

| File | Lines | sha256 (prefix) | Parity vs `classify()` |
|---|---|---|---|
| `training/router_sft/train.jsonl` | 160 | `3d323f12…` | 160/160 |
| `training/router_sft/val.jsonl` | 40 | `dcccd717…` | 40/40 |

## Fine-tuning jobs (Nebius Token Factory, LoRA SFT)

| Job | Base model | Suffix | Status (2026-10-19, 06:20 UTC) |
|---|---|---|---|
| `ftjob-092f8852685248e5af86ec97c6af04db` | `Qwen/Qwen3-0.6B` | `tattva-router-qwen06` | running — event `Training started` |
| `ftjob-b41c116dfb8a44e390d9947e974c873a` | `unsloth/gpt-oss-20b-BF16` | `tattva-router-oss20b` | running — event `Training started` |

Poll 2026-10-19 16:18 UTC (`--poll`): ambos jobs siguen `running` con
`trained_steps=0`, `total_steps=null`, `trained_tokens=0` — la API aún no
reporta pasos de entrenamiento para ninguno. Sin números inventados.

Both jobs reuse the same uploaded dataset/validation files. Hard datum from the live API
(better than the docs): the minimum `context_length` for fine-tuning is **8192** — a
request with 4096 is rejected with HTTP 422.

Driver: [`training/tf_post_train.py`](tf_post_train.py) — reads `NEBIUS_API_KEY` from the
environment, supports `--poll` / `--events`, and never prints the key.

## Merge

Two variants, on purpose:

- [`training/merge_lora_light.py`](merge_lora_light.py) — **zero-torch** merger (numpy +
  ml_dtypes only): streams the base safetensors shard-by-shard, applies `ΔW = (lora_B @
  lora_A) * (alpha / r)` per target tensor, and copies everything else verbatim. Refuses to
  produce a checkpoint if no adapter tensor matches the base (no silent no-ops).
- [`training/merge_lora_torch.py`](merge_lora_torch.py) — the official recipe (torch +
  peft) for GPU hosts.

Merge verification (updated when the Qwen job finishes): checksum of the merged shard,
unmatched-tensor report, and a sanity generation through the local runner. Until that
happens this section stays **PLANNED** — no invented numbers.

## Dedicated endpoint

A dedicated endpoint serving the FAST tier model — `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`,
H100×1, `eu-north1`, min=max=1 replica — was created via `POST /v0/dedicated_endpoints`
and verified with a real inference call:

- first call (cold start, model load): 36.5 s,
- second call (warm): **0.86 s**, reply `dedicated-endpoint-ok`.

Billing policy (official docs): provisioning and stopping are **not** billed; a running
replica is. Kill-switch: `PATCH /v0/dedicated_endpoints/{id}` with `enabled=false` stops it
(re-activating is the same call with `enabled=true`).

Serving the **fine-tuned** model would use the same mechanism with custom weights —
currently in **beta by invitation** (Support must enable it for the project). The request
is with the operator; the runbook is written and ready.
