#!/usr/bin/env python3
"""Fuse several LoRA adapters into ONE adapter (zero-torch, numpy only).

Exact fusion trick: for each module, the fused delta is the (weighted) sum of
the individual deltas. Since delta_i = B_i @ A_i, stacking works exactly:

    B_f = [ w1*s1*B1 , w2*s2*B2 , ... ]   (hstack over the rank axis)
    A_f = [ A1 ; A2 ; ... ]               (vstack over the rank axis)
    => B_f @ A_f = sum_i (w_i*s_i) * B_i @ A_i

where s_i is the adapter's own scale (lora_alpha / r). The per-adapter scale is
baked into the fused A/B weights, so the fused adapter's config is written with
``alpha_pattern == rank_pattern`` (per-module scale 1.0). Modules present in
only some adapters are carried over untouched (their scale still baked in).

Guarantees:
- Fails loudly on missing/incomplete adapter files, shape mismatch across
  adapters of the same module, or if there is nothing to fuse.
- Self-verifies after writing: re-reads the fused adapter and compares
  ``B_f @ A_f`` against the recomputed per-module sum for EVERY module.

Usage:
    python3 training/fuse_loras.py \
        --lora path/to/adapter_a --lora path/to/adapter_b \
        --weights 1.0,1.0 \
        --out path/to/fused_adapter [--verify]

The fused adapter is consumable by ``training/merge_lora_light.py`` (or the
official torch+peft path) exactly like any other LoRA adapter.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

_spec = importlib.util.spec_from_file_location(
    "merge_lora_light", Path(__file__).with_name("merge_lora_light.py")
)
_mlight = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mlight)

_PREFIXES = ("base_model.model.", "base_model.")


def _canon(stem: str) -> str:
    """Canonical module key: strip the PEFT 'base_model...' wrapper prefixes."""
    for pref in _PREFIXES:
        if stem.startswith(pref):
            return stem[len(pref):]
    return stem


def _lookup(pattern: dict, stem: str, default):
    if stem in pattern:
        return pattern[stem]
    tail = stem.rsplit(".", 1)[-1]
    if tail in pattern:
        return pattern[tail]
    return default


def _load_adapter(lora_dir: Path) -> dict:
    adapter_path = lora_dir / "adapter_model.safetensors"
    config_path = lora_dir / "adapter_config.json"
    if not adapter_path.exists() or not config_path.exists():
        sys.exit(f"adapter files not found in {lora_dir} (need adapter_model.safetensors + adapter_config.json)")
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    header, data = _mlight._read_header(adapter_path)
    modules: dict[str, dict] = {}
    for name in header:
        if name.endswith(".lora_A.weight"):
            stem = name[: -len(".lora_A.weight")]
            modules.setdefault(stem, {})["A"] = _mlight._tensor(header[name], data).astype(np.float32)
        elif name.endswith(".lora_B.weight"):
            stem = name[: -len(".lora_B.weight")]
            modules.setdefault(stem, {})["B"] = _mlight._tensor(header[name], data).astype(np.float32)
    if not modules:
        sys.exit(f"adapter contains no .lora_A/.lora_B tensors: {lora_dir}")
    incomplete = [m for m, t in modules.items() if "A" not in t or "B" not in t]
    if incomplete:
        sys.exit(f"adapter pairs incomplete in {lora_dir}: {incomplete[:5]}")

    rank_pattern = cfg.get("rank_pattern") or {}
    alpha_pattern = cfg.get("alpha_pattern") or {}
    r_default = int(cfg.get("r") or max((int(v) for v in rank_pattern.values()), default=0))
    alpha_default = float(cfg.get("lora_alpha", r_default))

    def scale_of(stem: str) -> float:
        rr = int(_lookup(rank_pattern, stem, r_default) or 0)
        aa = float(_lookup(alpha_pattern, stem, alpha_default))
        return (aa / rr) if rr else 1.0

    return {
        "dir": lora_dir,
        "config": cfg,
        "modules": modules,
        "scale_of": scale_of,
        "dtypes": {meta["dtype"] for meta in header.values()},
    }


def fuse(lora_dirs: list[Path], out_dir: Path, weights: list[float] | None = None) -> dict:
    if _mlight._BF16 is None:
        sys.exit("ml_dtypes is required (pip install ml_dtypes)")
    if not lora_dirs:
        sys.exit("at least one --lora is required")
    weights = list(weights) if weights else [1.0] * len(lora_dirs)
    if len(weights) != len(lora_dirs):
        sys.exit(f"--weights has {len(weights)} values for {len(lora_dirs)} adapters")

    adapters = [_load_adapter(d) for d in lora_dirs]

    fused: dict[str, dict] = {}
    for weight, ad in zip(weights, adapters):
        for stem, tens in ad["modules"].items():
            key = _canon(stem)
            entry = fused.setdefault(key, {"name": stem, "parts": [], "sources": []})
            scale = ad["scale_of"](stem) * float(weight)
            entry["parts"].append((tens["A"], tens["B"], scale))
            entry["sources"].append(str(ad["dir"]))
    if not fused:
        sys.exit("nothing to fuse")

    all_dtypes = set().union(*(ad["dtypes"] for ad in adapters))
    if len(all_dtypes) == 1:
        out_dtype_name = next(iter(all_dtypes))
    else:
        out_dtype_name = "F32"
    out_dtype = _mlight._DTYPES[out_dtype_name]

    out_tensors: list[tuple[str, bytes, str, tuple[int, ...]]] = []
    ranks: dict[str, int] = {}
    total_params = 0
    for key in sorted(fused):
        entry = fused[key]
        parts = entry["parts"]
        shapes = {(float(a.shape[1]), float(b.shape[0])) for a, b, _ in parts}
        if len(shapes) != 1:
            sys.exit(f"shape mismatch across adapters for {key}: {sorted(shapes)}")
        a_f = np.vstack([a * s for a, _, s in parts]).astype(out_dtype)
        b_f = np.hstack([b for _, b, _ in parts]).astype(out_dtype)
        ranks[key] = int(a_f.shape[0])
        total_params += a_f.size + b_f.size
        name = entry["name"]
        out_tensors.append((f"{name}.lora_A.weight", a_f.tobytes(), out_dtype_name, tuple(a_f.shape)))
        out_tensors.append((f"{name}.lora_B.weight", b_f.tobytes(), out_dtype_name, tuple(b_f.shape)))

    max_rank = max(ranks.values())
    first_cfg = adapters[0]["config"]
    cfg = {
        "base_model_name_or_path": first_cfg.get("base_model_name_or_path"),
        "peft_type": "LORA",
        "task_type": first_cfg.get("task_type", "CAUSAL_LM"),
        "bias": "none",
        "fan_in_fan_out": False,
        "inference_mode": True,
        "lora_dropout": 0.0,
        "r": max_rank,
        "lora_alpha": max_rank,
        "rank_pattern": {k: v for k, v in ranks.items() if v != max_rank},
        "alpha_pattern": {k: v for k, v in ranks.items() if v != max_rank},
        "target_modules": sorted({k.rsplit(".", 1)[-1] for k in fused}),
        "use_rslora": False,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    _mlight._write_safetensors(out_dir / "adapter_model.safetensors", out_tensors)
    (out_dir / "adapter_config.json").write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")

    verify = _verify_fused(out_dir, fused)
    report = {
        "status": "ok",
        "adapters": [str(d) for d in lora_dirs],
        "weights": weights,
        "modules": len(fused),
        "rank_min": min(ranks.values()),
        "rank_max": max_rank,
        "params": total_params,
        "dtype": out_dtype_name,
        "out_dir": str(out_dir),
        "verify": verify,
    }
    (out_dir / "fuse_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _verify_fused(out_dir: Path, fused: dict) -> dict:
    """Re-read the fused adapter and compare B_f @ A_f vs the recomputed sum."""
    header, data = _mlight._read_header(out_dir / "adapter_model.safetensors")
    worst = 0.0
    checked = 0
    for key in sorted(fused):
        entry = fused[key]
        a_name = f"{entry['name']}.lora_A.weight"
        b_name = f"{entry['name']}.lora_B.weight"
        out_dt = _mlight._DTYPES[header[a_name]["dtype"]]
        a_f = _mlight._tensor(header[a_name], data).astype(np.float32)
        b_f = _mlight._tensor(header[b_name], data).astype(np.float32)
        got = b_f @ a_f
        expected = sum(s * (b @ a) for a, b, s in entry["parts"]).astype(out_dt).astype(np.float32)
        scale = max(1.0, float(np.abs(expected).max()))
        err = float(np.abs(got - expected).max()) / scale
        worst = max(worst, err)
        checked += 1
        if err > 1e-3:
            sys.exit(f"self-verification failed for {key}: rel err {err:.2e}")
    return {"verified_modules": checked, "worst_rel_err": worst}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lora", action="append", required=True,
                        help="LoRA adapter directory (repeat for each adapter)")
    parser.add_argument("--weights", default=None,
                        help="comma-separated per-adapter weights (default: all 1.0)")
    parser.add_argument("--out", required=True, help="output directory for the fused adapter")
    parser.add_argument("--verify", action="store_true", help="re-check the fused adapter (always done internally; flag kept for symmetry)")
    args = parser.parse_args()

    weights = None
    if args.weights:
        try:
            weights = [float(w) for w in args.weights.split(",")]
        except ValueError:
            sys.exit(f"invalid --weights: {args.weights!r}")
    report = fuse([Path(p) for p in args.lora], Path(args.out), weights)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
