"""Tests for multi-adapter LoRA fusion (training/fuse_loras.py).

Builds synthetic adapters, fuses them, and checks (a) the exact math
B_f @ A_f == sum_i w_i * s_i * (B_i @ A_i), (b) carry-over of modules that
exist in only one adapter, (c) loud refusal on shape mismatch, and (d) the
full pipeline: fused adapter + merge_lora_light into a base checkpoint.
"""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

ml_dtypes = pytest.importorskip("ml_dtypes")
bf16 = ml_dtypes.bfloat16

ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "training" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fl = _load("fuse_loras")
mlight = fl._mlight


def _write_adapter(path: Path, modules: dict, r: int, alpha: float, prefix: str = "base_model.model.model.layers.0"):
    path.mkdir(parents=True, exist_ok=True)
    entries = []
    for stem, (a, b) in modules.items():
        full = f"{prefix}.{stem}"
        entries.append((f"{full}.lora_A.weight", a.tobytes(), mlight._NAME_BY_DTYPE[a.dtype.type], tuple(a.shape)))
        entries.append((f"{full}.lora_B.weight", b.tobytes(), mlight._NAME_BY_DTYPE[b.dtype.type], tuple(b.shape)))
    mlight._write_safetensors(path / "adapter_model.safetensors", entries)
    (path / "adapter_config.json").write_text(
        json.dumps({"r": r, "lora_alpha": alpha, "base_model_name_or_path": "synthetic/base"})
    )


def _read_adapter(path: Path):
    header, data = mlight._read_header(path / "adapter_model.safetensors")
    out = {}
    for name in header:
        if name.endswith(".lora_A.weight"):
            out.setdefault(name[: -len(".lora_A.weight")], {})["A"] = mlight._tensor(header[name], data).astype(np.float32)
        elif name.endswith(".lora_B.weight"):
            out.setdefault(name[: -len(".lora_B.weight")], {})["B"] = mlight._tensor(header[name], data).astype(np.float32)
    return out, json.loads((path / "adapter_config.json").read_text())


def test_fuse_math_exact(tmp_path):
    rng = np.random.default_rng(7)
    q1 = (rng.standard_normal((2, 6)) * 0.1).astype(np.float32)
    q1b = (rng.standard_normal((4, 2)) * 0.1).astype(np.float32)
    q2 = (rng.standard_normal((2, 6)) * 0.1).astype(np.float32)
    q2b = (rng.standard_normal((4, 2)) * 0.1).astype(np.float32)

    a1 = _write_adapter(tmp_path / "a1", {"self_attn.q_proj": (q1, q1b)}, r=2, alpha=4)  # scale 2.0
    a1_dir = tmp_path / "a1"
    a2_dir = tmp_path / "a2"
    _write_adapter(a2_dir, {"self_attn.q_proj": (q2, q2b)}, r=2, alpha=2)  # scale 1.0

    out = tmp_path / "fused"
    report = fl.fuse([a1_dir, a2_dir], out)
    assert report["status"] == "ok"
    assert report["modules"] == 1
    assert report["rank_max"] == 4

    modules, cfg = _read_adapter(out)
    assert set(modules) == {"base_model.model.model.layers.0.self_attn.q_proj"}
    fused = modules["base_model.model.model.layers.0.self_attn.q_proj"]
    assert fused["A"].shape == (4, 6)
    assert fused["B"].shape == (4, 4)
    expected = 2.0 * (q1b @ q1) + 1.0 * (q2b @ q2)
    np.testing.assert_allclose(fused["B"] @ fused["A"], expected, rtol=1e-5, atol=1e-6)
    assert cfg["r"] == 4 and cfg["lora_alpha"] == 4  # global scale 1.0


def test_fuse_carries_modules_present_in_one_adapter(tmp_path):
    rng = np.random.default_rng(11)
    ax, bx = rng.standard_normal((2, 5)).astype(np.float32), rng.standard_normal((3, 2)).astype(np.float32)
    ay, by = rng.standard_normal((2, 7)).astype(np.float32), rng.standard_normal((3, 2)).astype(np.float32)
    d1, d2 = tmp_path / "d1", tmp_path / "d2"
    _write_adapter(d1, {"self_attn.k_proj": (ax, bx)}, r=2, alpha=2)
    _write_adapter(d2, {"mlp.gate_proj": (ay, by)}, r=2, alpha=2)

    out = tmp_path / "fused"
    fl.fuse([d1, d2], out)
    modules, _ = _read_adapter(out)
    k = modules["base_model.model.model.layers.0.self_attn.k_proj"]
    g = modules["base_model.model.model.layers.0.mlp.gate_proj"]
    np.testing.assert_allclose(k["B"] @ k["A"], bx @ ax, rtol=1e-5, atol=1e-6)
    np.testing.assert_allclose(g["B"] @ g["A"], by @ ay, rtol=1e-5, atol=1e-6)


def test_fuse_applies_weights(tmp_path):
    rng = np.random.default_rng(3)
    a1, b1 = rng.standard_normal((2, 6)).astype(np.float32), rng.standard_normal((4, 2)).astype(np.float32)
    a2, b2 = rng.standard_normal((2, 6)).astype(np.float32), rng.standard_normal((4, 2)).astype(np.float32)
    d1, d2 = tmp_path / "d1", tmp_path / "d2"
    _write_adapter(d1, {"self_attn.o_proj": (a1, b1)}, r=2, alpha=4)
    _write_adapter(d2, {"self_attn.o_proj": (a2, b2)}, r=2, alpha=4)
    out = tmp_path / "fused"
    fl.fuse([d1, d2], out, weights=[0.5, 2.0])
    modules, _ = _read_adapter(out)
    fused = modules["base_model.model.model.layers.0.self_attn.o_proj"]
    expected = 0.5 * 2.0 * (b1 @ a1) + 2.0 * 2.0 * (b2 @ a2)
    np.testing.assert_allclose(fused["B"] @ fused["A"], expected, rtol=1e-5, atol=1e-6)


def test_fuse_refuses_shape_mismatch(tmp_path):
    rng = np.random.default_rng(5)
    d1, d2 = tmp_path / "d1", tmp_path / "d2"
    _write_adapter(d1, {"self_attn.q_proj": (rng.standard_normal((2, 6)).astype(np.float32), rng.standard_normal((4, 2)).astype(np.float32))}, r=2, alpha=2)
    _write_adapter(d2, {"self_attn.q_proj": (rng.standard_normal((2, 5)).astype(np.float32), rng.standard_normal((4, 2)).astype(np.float32))}, r=2, alpha=2)
    with pytest.raises(SystemExit, match="shape mismatch"):
        fl.fuse([d1, d2], tmp_path / "fused")


def test_fused_adapter_merges_into_base(tmp_path):
    rng = np.random.default_rng(13)
    w = rng.standard_normal((4, 6)).astype(np.float32).astype(bf16)
    a1, b1 = rng.standard_normal((2, 6)).astype(np.float32), rng.standard_normal((4, 2)).astype(np.float32)
    a2, b2 = rng.standard_normal((1, 6)).astype(np.float32), rng.standard_normal((4, 1)).astype(np.float32)

    base = tmp_path / "base"
    base.mkdir()
    mlight._write_safetensors(base / "model.safetensors", [("lq.weight", w.tobytes(), "BF16", (4, 6))])
    (base / "config.json").write_text('{"model_type":"synthetic"}')

    d1, d2 = tmp_path / "d1", tmp_path / "d2"
    for d, (a, b), alpha in ((d1, (a1, b1), 4.0), (d2, (a2, b2), 1.0)):
        d.mkdir()
        entries = [
            ("lq.lora_A.weight", a.tobytes(), "F32", tuple(a.shape)),
            ("lq.lora_B.weight", b.tobytes(), "F32", tuple(b.shape)),
        ]
        mlight._write_safetensors(d / "adapter_model.safetensors", entries)
        (d / "adapter_config.json").write_text(json.dumps({"r": a.shape[0] if a.shape[0] == 2 else 1, "lora_alpha": alpha}))

    fused, merged = tmp_path / "fused", tmp_path / "merged"
    fl.fuse([d1, d2], fused)
    report = mlight.merge(base, fused, merged)
    assert report["status"] == "ok" and report["scale"] == 1.0

    header, data = mlight._read_header(merged / "model.safetensors")
    got = mlight._tensor(header["lq.weight"], data)
    expected = (w.astype(np.float32) + 2.0 * (b1 @ a1) + 1.0 * (b2 @ a2)).astype(bf16)
    diff = np.abs(got.astype(np.float32) - expected.astype(np.float32))
    bound = np.abs(expected.astype(np.float32)) * 0.02 + 0.05
    assert np.all(diff <= bound), f"max diff {diff.max():.4f}"
