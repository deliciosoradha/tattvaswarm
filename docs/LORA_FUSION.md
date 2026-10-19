# LoRA fusion — accumulating adapters (zero-torch)

Status: **VERIFIED** (`training/fuse_loras.py`, 5 tests) and exercised on the
real adapters; merging into the base checkpoint is done by
`training/merge_lora_light.py` (see also `docs/POST_TRAINING.md`).

## Why fuse instead of stacking

Inference hardware is CPU-scale and the accumulated personal adapters are
small r=16/32 LoRAs. Loading N adapters per request means N adapter reads and
N delta applications; fusing them into **one** adapter with the same rank
structure keeps a single hot path and one artifact to ship.

## The math (exact rank concatenation)

For every targeted module, with per-adapter scale `s_i = alpha_i / r_i`:

```
B_f = [ s_1·B_1 | s_2·B_2 | … ]     (hstack, shape [out, Σr_i])
A_f = [ A_1 ; A_2 ; … ]             (vstack, shape [Σr_i, in])
ΔW  = B_f @ A_f = Σ_i s_i·(B_i @ A_i)
```

The per-adapter scale is **baked into B**, and the fused `adapter_config.json`
sets `alpha_pattern == rank_pattern == r_i` per module, so PEFT computes
`scale = 1.0` for every module — no double-scaling.

Details that matter in practice:

- **Mixed dtypes**: adapters coming from different training stacks (f16/bf16)
  are promoted to **f32** for the fused output. The equality check below
  proves nothing is lost beyond f32 rounding.
- **Per-module ranks**: targets are only fusible when every adapter that
  touches a module targets it with compatible in/out dims; modules covered by
  a subset of adapters simply use that subset (the union of stems is walked).
- **Refusals are loud**: dimension mismatches abort with an explicit message;
  the tool never silently emits a partial fusion.

## Verification

For every module, the tool recomputes the expected delta from the fused
factorization and compares it to `Σ s_i·(B_i@A_i)`:

- 168/168 modules verified, worst relative error **6.98e-10**
- 9,879,552 fused parameters (f32), ranks 16–32 per module
- real run: ALICE (`Qwen2.5-0.5B` q/v) + jyotish `lora_0p5b` (7 module kinds ×
  24 layers) → single adapter, weights `[1.0, 1.0]`
- artifact sha256: `73d50c4f9c7993168887dfdce6fe007c00190c75744c274f5030dfb70cdb3f43`

## Merge into the base checkpoint

`training/merge_lora_light.py` melts the fused adapter into the base
safetensors (the Token Factory merge recipe, re-implemented dependency-free):

- `W_merged = W_base + scale·(B_f @ A_f)` per module, other tensors copied
  byte-for-byte, dtypes preserved, sharded files handled.
- **PEFT prefix compatibility (fixed 2026-10-19)**: real PEFT adapters name
  tensors `base_model.model.model.layers…`, while HF base checkpoints use
  `model.layers…`. The merge now matches stems leniently across both
  conventions (raw, `base_model.model.`, `base_model.` prefixes), with a
  regression test. Before the fix the tool correctly refused:
  `no base tensors matched the adapter; refusing to produce an unmerged checkpoint`.
- Emits a report: merged tensor count, per-module worst relative error,
  unused adapter stems (must be empty).

## Reproduce

```bash
python3 training/fuse_loras.py \
  --adapter alice=…/cpu-lora/final --adapter jyotish=…/lora_0p5b \
  --out tf-training/fused-alice-jyotish --verify

python3 training/merge_lora_light.py \
  --base …/base_0p5b --lora tf-training/fused-alice-jyotish \
  --out …/merged-alice-jyotish-0p5b --verify
```

`--verify` on the merge adds the round-trip check against the sources, so a
green run is enough to ship the checkpoint.
