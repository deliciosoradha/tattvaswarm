#!/usr/bin/env python3
"""Zero-torch LoRA merge — bake LoRA adapters into base weights (safetensors in/out).

Lightweight companion to the official torch+peft merge script (see
``training/merge_lora_torch.py``, which follows the Nebius Token Factory
post-training guide). This variant reads and writes the safetensors format
directly with numpy (plus ``ml_dtypes`` for bfloat16), so it runs on machines
without torch, using bounded memory (one tensor at a time).

Math (standard LoRA):   W' = W + (lora_alpha / r) * (B @ A)

Guarantees:
- Every base tensor paired with adapter tensors is merged; everything else is
  copied byte-for-byte.
- Fails loudly when (a) adapter tensors cannot be paired with the base, or
  (b) shapes are incompatible. No silent partial merges.

Usage:
    python3 training/merge_lora_light.py \
        --base path/to/base-ckpt --lora path/to/adapter --out path/to/merged \
        [--verify]
"""

from __future__ import annotations

import argparse
import json
import shutil
import struct
import sys
from pathlib import Path

import numpy as np

try:
    import ml_dtypes

    _BF16 = ml_dtypes.bfloat16
except ImportError:  # pragma: no cover - exercised only without ml_dtypes
    _BF16 = None

_DTYPES = {
    "F64": np.float64,
    "F32": np.float32,
    "F16": np.float16,
    "BF16": _BF16,
    "I64": np.int64,
    "I32": np.int32,
    "I16": np.int16,
    "I8": np.int8,
    "U8": np.uint8,
    "BOOL": np.bool_,
}
_FLOAT_REVERSE = {np.float64: "F64", np.float32: "F32", np.float16: "F16"}
if _BF16 is not None:
    _FLOAT_REVERSE[_BF16] = "BF16"
_NAME_BY_DTYPE = {v: k for k, v in _DTYPES.items() if v is not None}


def _read_header(path: Path) -> tuple[dict, bytes]:
    """Return (tensor metadata, raw data bytes) for one safetensors file."""
    raw = path.read_bytes()
    header_len = struct.unpack("<Q", raw[:8])[0]
    header = json.loads(raw[8 : 8 + header_len].decode("utf-8"))
    data = raw[8 + header_len :]
    return {k: v for k, v in header.items() if k != "__metadata__"}, data


def _tensor(meta: dict, data: bytes) -> np.ndarray:
    dtype = _DTYPES[meta["dtype"]]
    start, end = meta["data_offsets"]
    return np.frombuffer(data[start:end], dtype=dtype).reshape(meta["shape"])


def _write_safetensors(path: Path, tensors: list[tuple[str, bytes, str, tuple[int, ...]]]) -> None:
    """Write tensors = [(name, raw_bytes, dtype_name, shape), ...]."""
    offset = 0
    header: dict[str, dict] = {}
    for name, payload, dtype_name, shape in tensors:
        header[name] = {
            "dtype": dtype_name,
            "shape": list(shape),
            "data_offsets": [offset, offset + len(payload)],
        }
        offset += len(payload)
    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    pad = (-(len(header_bytes) + 8)) % 8
    header_bytes += b" " * pad
    with open(path, "wb") as fh:
        fh.write(struct.pack("<Q", len(header_bytes)))
        fh.write(header_bytes)
        for _name, payload, _dtype_name, _shape in tensors:
            fh.write(payload)


def merge(base_dir: Path, lora_dir: Path, out_dir: Path) -> dict:
    if _BF16 is None:
        sys.exit("ml_dtypes is required (pip install ml_dtypes)")

    adapter_path = lora_dir / "adapter_model.safetensors"
    config_path = lora_dir / "adapter_config.json"
    if not adapter_path.exists() or not config_path.exists():
        sys.exit(f"adapter files not found in {lora_dir} (need adapter_model.safetensors + adapter_config.json)")

    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    r = int(cfg["r"])
    alpha = float(cfg.get("lora_alpha", r))
    scale = alpha / r

    lora_header, lora_data = _read_header(adapter_path)
    pairs: dict[str, tuple[str, str]] = {}
    for name in lora_header:
        if name.endswith(".lora_A.weight"):
            stem = name[: -len(".lora_A.weight")]
            pairs.setdefault(stem, ("", ""))
            pairs[stem] = (name, pairs[stem][1])
        elif name.endswith(".lora_B.weight"):
            stem = name[: -len(".lora_B.weight")]
            pairs.setdefault(stem, ("", ""))
            pairs[stem] = (pairs[stem][0], name)
    if not pairs:
        sys.exit("adapter contains no .lora_A/.lora_B tensors")
    missing = [stem for stem, (a, b) in pairs.items() if not a or not b]
    if missing:
        sys.exit(f"adapter pairs incomplete for: {missing[:5]}")

    def pair_key_for(stem: str) -> str | None:
        """PEFT adapters carry a 'base_model.model.' wrapper prefix; base
        checkpoints (HF) do not. Match leniently across both conventions."""
        for candidate in (stem, f"base_model.model.{stem}", f"base_model.{stem}"):
            if candidate in pairs:
                return candidate
        return None

    out_dir.mkdir(parents=True, exist_ok=True)
    merged_count = 0
    used_stems: set[str] = set()

    for shard in sorted(base_dir.glob("*.safetensors")):
        header, data = _read_header(shard)
        out_tensors: list[tuple[str, bytes, str, tuple[int, ...]]] = []
        for name, meta in header.items():
            payload = data[meta["data_offsets"][0] : meta["data_offsets"][1]]
            stem = name[: -len(".weight")] if name.endswith(".weight") else None
            key = pair_key_for(stem) if stem is not None else None
            if key is not None:
                a_name, b_name = pairs[key]
                a = _tensor(lora_header[a_name], lora_data).astype(np.float32)
                b = _tensor(lora_header[b_name], lora_data).astype(np.float32)
                w = _tensor(meta, data).astype(np.float32)
                delta = b @ a
                if delta.shape != w.shape:
                    sys.exit(f"shape mismatch for {name}: base {w.shape} vs delta {delta.shape}")
                merged = (w + scale * delta).astype(_DTYPES[meta["dtype"]])
                out_tensors.append((name, merged.tobytes(), meta["dtype"], tuple(meta["shape"])))
                merged_count += 1
                used_stems.add(key)
            else:
                out_tensors.append((name, payload, meta["dtype"], tuple(meta["shape"])))
        _write_safetensors(out_dir / shard.name, out_tensors)

    if merged_count == 0:
        sys.exit("no base tensors matched the adapter; refusing to produce an unmerged checkpoint")
    unused = sorted(set(pairs) - used_stems)
    if unused:
        sys.exit(f"adapter tensors were never merged (base missing?): {unused[:5]}")

    for path in base_dir.iterdir():
        if path.is_file() and not path.name.endswith(".safetensors"):
            shutil.copy(path, out_dir / path.name)

    report = {
        "status": "ok",
        "scale": scale,
        "r": r,
        "lora_alpha": alpha,
        "merged_tensors": merged_count,
        "shards": len(list(base_dir.glob("*.safetensors"))),
        "out_dir": str(out_dir),
    }
    return report


def verify(merged_dir: Path) -> dict:
    """Roundtrip check: re-read the merged shards and re-parse their headers."""
    checked = 0
    total_bytes = 0
    for shard in sorted(merged_dir.glob("*.safetensors")):
        header, data = _read_header(shard)
        for meta in header.values():
            start, end = meta["data_offsets"]
            if end - start != int(np.prod(meta["shape"])) * np.dtype(_DTYPES[meta["dtype"]]).itemsize:
                sys.exit(f"bad size for a tensor in {shard.name}")
            checked += 1
            total_bytes += end - start
        if len(data) != max(m["data_offsets"][1] for m in header.values()):
            sys.exit(f"trailing bytes in {shard.name}")
    return {"status": "ok", "verified_tensors": checked, "total_bytes": total_bytes}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="base checkpoint directory (safetensors)")
    parser.add_argument("--lora", required=True, help="LoRA adapter directory (adapter_model.safetensors + adapter_config.json)")
    parser.add_argument("--out", required=True, help="output directory for the merged checkpoint")
    parser.add_argument("--verify", action="store_true", help="re-read the merged shards and validate sizes")
    args = parser.parse_args()

    report = merge(Path(args.base), Path(args.lora), Path(args.out))
    if args.verify:
        report["verify"] = verify(Path(args.out))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
