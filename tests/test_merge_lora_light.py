"""Tests for the zero-torch LoRA merge (training/merge_lora_light.py).

Builds a tiny synthetic bf16 "model" + LoRA adapter in a temp dir, merges,
and checks the math (W' == W + scale * B @ A) and the byte-for-byte copies.
"""

import importlib.util
import json
import struct
import sys
from pathlib import Path

import numpy as np
import pytest

ml_dtypes = pytest.importorskip("ml_dtypes")
bf16 = ml_dtypes.bfloat16

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("merge_lora_light", ROOT / "training" / "merge_lora_light.py")
mlight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mlight)


def _write(path: Path, tensors: dict[str, np.ndarray]) -> None:
    entries = []
    for name, arr in tensors.items():
        entries.append((name, arr.tobytes(), mlight._NAME_BY_DTYPE[arr.dtype.type], tuple(arr.shape)))
    mlight._write_safetensors(path, entries)


def _read(path: Path) -> dict[str, np.ndarray]:
    header, data = mlight._read_header(path)
    return {name: mlight._tensor(meta, data) for name, meta in header.items()}


def test_merge_math_and_copies(tmp_path):
    base, lora, out = tmp_path / "base", tmp_path / "lora", tmp_path / "out"
    base.mkdir()
    lora.mkdir()

    rng = np.random.default_rng(7)
    w_q = rng.standard_normal((4, 6)).astype(np.float32).astype(bf16)
    w_up = rng.standard_normal((3, 6)).astype(np.float32).astype(bf16)
    w_plain = rng.standard_normal((2, 2)).astype(np.float32).astype(bf16)
    _write(base / "model.safetensors", {"l_q.weight": w_q, "l_up.weight": w_up, "l_plain.weight": w_plain})
    (base / "config.json").write_text('{"model_type":"synthetic"}')

    a_q = (rng.standard_normal((2, 6)) * 0.1).astype(np.float32).astype(bf16)
    b_q = (rng.standard_normal((4, 2)) * 0.1).astype(np.float32).astype(bf16)
    _write(lora / "adapter_model.safetensors", {"l_q.lora_A.weight": a_q, "l_q.lora_B.weight": b_q})
    (lora / "adapter_config.json").write_text(json.dumps({"r": 2, "lora_alpha": 4}))

    report = mlight.merge(base, lora, out)
    assert report["status"] == "ok"
    assert report["merged_tensors"] == 1  # only l_q is adapted
    assert report["scale"] == 2.0

    got = _read(out / "model.safetensors")
    expected = (w_q.astype(np.float32) + 2.0 * (b_q.astype(np.float32) @ a_q.astype(np.float32))).astype(bf16)
    assert np.array_equal(got["l_q.weight"], expected)
    assert np.array_equal(got["l_up.weight"], w_up)  # untouched
    assert (out / "config.json").read_text() == '{"model_type":"synthetic"}'  # copied
    assert mlight.verify(out)["verified_tensors"] == 3


def test_merge_refuses_unused_adapter(tmp_path):
    base, lora, out = tmp_path / "base", tmp_path / "lora", tmp_path / "out"
    base.mkdir()
    lora.mkdir()
    _write(base / "model.safetensors", {"only.weight": np.zeros((2, 2), dtype=bf16)})
    _write(
        lora / "adapter_model.safetensors",
        {
            "ghost.lora_A.weight": np.zeros((1, 2), dtype=bf16),
            "ghost.lora_B.weight": np.zeros((2, 1), dtype=bf16),
        },
    )
    (lora / "adapter_config.json").write_text(json.dumps({"r": 1, "lora_alpha": 1}))

    with pytest.raises(SystemExit, match="no base tensors matched"):
        mlight.merge(base, lora, out)


def test_merge_matches_prefixed_adapter_names(tmp_path):
    """Real PEFT adapters carry a 'base_model.model.' prefix while HF base
    checkpoints do not; the merge must match across both conventions."""
    base, lora, out = tmp_path / "base", tmp_path / "lora", tmp_path / "out"
    base.mkdir()
    lora.mkdir()
    w = np.arange(24, dtype=np.float32).reshape(4, 6).astype(bf16)
    _write(base / "model.safetensors", {"model.layers.0.self_attn.q_proj.weight": w})
    a = np.full((2, 6), 0.5, dtype=np.float32).astype(bf16)
    b = np.full((4, 2), 1.0, dtype=np.float32).astype(bf16)
    _write(
        lora / "adapter_model.safetensors",
        {
            "base_model.model.model.layers.0.self_attn.q_proj.lora_A.weight": a,
            "base_model.model.model.layers.0.self_attn.q_proj.lora_B.weight": b,
        },
    )
    (lora / "adapter_config.json").write_text(json.dumps({"r": 2, "lora_alpha": 4}))

    report = mlight.merge(base, lora, out)
    assert report["merged_tensors"] == 1
    got = _read(out / "model.safetensors")["model.layers.0.self_attn.q_proj.weight"]
    expected = (w.astype(np.float32) + 2.0 * (b.astype(np.float32) @ a.astype(np.float32))).astype(bf16)
    assert np.array_equal(got, expected)
