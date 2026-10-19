# Nebius Token Factory — model tiers and verified usage

All LLM reasoning in TattvaSwarm goes through **Nebius Token Factory**
(OpenAI-compatible API, base URL `https://api.tokenfactory.nebius.com/v1/`).
This keeps the project honest and simple: one API key, open models, and a
measured usage ledger that stays on your machine.

## Verified catalog (2026-10-19)

`GET /v1/models` → **HTTP 200**, 28 models visible, **5 NVIDIA / Nemotron**:

| Model ID | Role |
|---|---|
| `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | fast tier — everyday calls |
| `nvidia/nemotron-3-super-120b-a12b` | reasoning tier — serious reasoning |
| `nvidia/Nemotron-3-Ultra-550b-a55b` | heavy tier — long synthesis |
| `nvidia/Nemotron-3.5-Super-VL` | optional vision demos |
| `nvidia/Nemotron-3_5-Lightning` | alternative fast tier |

(Catalog also includes Hermes-4-405B, Qwen, DeepSeek, GLM and others — see
`scripts/smoke_token_factory.py --list-models`.)

## Tier map (as shipped in `.env.example`)

| Router tier | Backend | Verified live |
|---|---|---|
| `small` | local deterministic (no LLM) | — |
| `normal` | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | HTTP 200 · replies in ~0.9–2.9 s |
| `reasoning` | `nvidia/nemotron-3-super-120b-a12b` | HTTP 200 · ~1.9 s |
| `heavy` | `nvidia/Nemotron-3-Ultra-550b-a55b` | HTTP 200 · ~1.6 s |
| `research` | Tavily search (optional, needs `TAVILY_API_KEY`) | not run without key — honest error |

Latencies measured with `temperature=0`, short prompts, from a low-power host
(2026-10-19). The Nemotron models are *thinking* models: small `max_tokens`
budgets can be consumed by reasoning tokens before any visible content is
emitted (observed: `content: null` with a 48-token budget; fine once budget
was raised). Give headroom, or use them for reasoning-heavy calls.

## How to verify yourself

```bash
python scripts/smoke_token_factory.py --list-models
python scripts/smoke_token_factory.py --model nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B \
    --prompt "Reply with exactly: TATTVA_OK"
```

## Honesty rules

- No key / no model configured → the router returns a structured `error` with
  the exact reason (and the CLI exits non-zero). It **never fabricates**.
- Every successful call is appended to `$TATTVA_HOME/usage.jsonl`
  (model, token usage, latency). The ledger is local-only.
