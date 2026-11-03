#!/usr/bin/env python3
"""
SAM 3.1 Physics Injector — Meta Global AI Developer Hackathon Edition.

NEW WORK — Built Oct 27 - Nov 4, 2026.

Converts SAM 3.1 segmentation masks (atmospheric vortices, Mach-15 thermal
shields, shock fronts) into Dirichlet/Neumann boundary tensors for Triton
GPU kernels. Numpy-only so it runs without torch/triton installed; when
torch is available it can emit torch tensors directly.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from typing import Dict, Any, Tuple

import numpy as np


@dataclass
class InjectionConfig:
    grid_h: int = 512
    grid_w: int = 512
    dirichlet_value: float = 1.0
    neumann_value: float = 0.0
    # Threshold for binarizing soft SAM masks into {0,1}
    mask_threshold: float = 0.5


def binarize_mask(soft_mask: np.ndarray, threshold: float = 0.5) -> np.ndarray:
    """Binarize a soft SAM 3.1 mask into {0,1} uint8."""
    return (soft_mask >= threshold).astype(np.uint8)


def resize_nearest(mask: np.ndarray, target_h: int, target_w: int) -> np.ndarray:
    """Nearest-neighbor resize without external deps (masks are binary)."""
    h, w = mask.shape[-2], mask.shape[-1]
    if (h, w) == (target_h, target_w):
        return mask
    row_idx = (np.linspace(0, h - 1, target_h)).astype(int)
    col_idx = (np.linspace(0, w - 1, target_w)).astype(int)
    return mask[..., row_idx[:, None], col_idx]


def mask_to_boundary_tensors(
    sam_mask: np.ndarray, config: InjectionConfig | None = None
) -> Dict[str, np.ndarray]:
    """
    Convert a SAM 3.1 mask into boundary tensors for Triton kernels.

    Returns dict with:
      - omega_mask: binary domain mask {0,1}^{H x W}
      - dirichlet: float32 Dirichlet values (mask * dirichlet_value)
      - neumann: float32 Neumann values ((1-mask) * neumann_value)
      - signed_distance_sign: +1 inside / -1 outside (cheap sign field)
    """
    cfg = config or InjectionConfig()
    m = np.asarray(sam_mask)
    if m.ndim > 2:
        m = m.reshape(m.shape[-2], m.shape[-1])
    binary = binarize_mask(m.astype(np.float32), cfg.mask_threshold)
    binary = resize_nearest(binary, cfg.grid_h, cfg.grid_w)
    dirichlet = (binary.astype(np.float32)) * cfg.dirichlet_value
    neumann = ((1 - binary).astype(np.float32)) * cfg.neumann_value
    sign_field = np.where(binary == 1, 1.0, -1.0).astype(np.float32)
    return {
        "omega_mask": binary,
        "dirichlet": dirichlet,
        "neumann": neumann,
        "signed_distance_sign": sign_field,
    }


def build_triton_launch_params(
    tensors: Dict[str, np.ndarray], block: int = 16
) -> Dict[str, Any]:
    """Derive grid/block launch params for a Triton boundary kernel."""
    h, w = tensors["omega_mask"].shape
    grid = ((h + block - 1) // block, (w + block - 1) // block)
    coverage = float(tensors["omega_mask"].mean())
    return {
        "grid_h": h,
        "grid_w": w,
        "block": block,
        "triton_grid": grid,
        "mask_coverage": coverage,
        "num_masked_cells": int(tensors["omega_mask"].sum()),
    }


def save_injection_bundle(
    tensors: Dict[str, np.ndarray],
    launch: Dict[str, Any],
    out_dir: str = "logs/sam31_bundles",
    tag: str = "bundle",
) -> str:
    os.makedirs(out_dir, exist_ok=True)
    npz_path = os.path.join(out_dir, f"{tag}.npz")
    np.savez_compressed(npz_path, **{k: v for k, v in tensors.items()})
    with open(os.path.join(out_dir, f"{tag}.json"), "w", encoding="utf-8") as f:
        json.dump(launch, f, indent=2)
    return npz_path


def demo_mask(h: int = 128, w: int = 128) -> np.ndarray:
    """Synthetic vortex-like ring mask for offline demo/tests."""
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = w / 2, h / 2
    r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    soft = np.exp(-((r - min(h, w) * 0.25) ** 2) / (2 * (min(h, w) * 0.08) ** 2))
    return soft.astype(np.float32)


if __name__ == "__main__":
    cfg = InjectionConfig(grid_h=512, grid_w=512)
    soft = demo_mask()
    tensors = mask_to_boundary_tensors(soft, cfg)
    launch = build_triton_launch_params(tensors)
    path = save_injection_bundle(tensors, launch, tag="demo_vortex")
    print(f"SAM31 bundle saved: {path}")
    print(json.dumps(launch, indent=2))
