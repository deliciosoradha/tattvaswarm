import pytest
import numpy as np
import sys
import os

# Anadir benchmarks al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "benchmarks"))
from audit_rigorous_harness import reference_cpu_fp64

def test_reference_fp64_determinism():
    """Verifica determinismo absoluto en corridas sucesivas de la referencia FP64."""
    N = 10_000
    phase = np.linspace(0, 4.0 * np.pi, N, dtype=np.float64)
    u_in = 25.0 * np.sin(phase * 2.0) + 8.5 * np.cos(phase * 6.0)

    u1, enstrophy1 = reference_cpu_fp64(u_in)
    u2, enstrophy2 = reference_cpu_fp64(u_in)

    np.testing.assert_array_equal(u1, u2)
    assert enstrophy1 == enstrophy2
    assert enstrophy1 > 0.0

def test_fp32_vs_fp64_numerical_precision():
    """Verifica que la precision FP32 cumple la cota L2 <= 1e-5 y Linf <= 5e-5 contra FP64."""
    N = 50_000
    phase = np.linspace(0, 4.0 * np.pi, N, dtype=np.float64)
    u_in_64 = 25.0 * np.sin(phase * 2.0) + 8.5 * np.cos(phase * 6.0)
    u_in_32 = u_in_64.astype(np.float32)

    u_ref_64, _ = reference_cpu_fp64(u_in_64)
    u_eval_32, _ = reference_cpu_fp64(u_in_32)

    # Calcular normas relativas
    u_eval_promoted = u_eval_32.astype(np.float64)
    rel_l2 = np.linalg.norm(u_eval_promoted - u_ref_64) / np.linalg.norm(u_ref_64)
    abs_linf = np.max(np.abs(u_eval_promoted - u_ref_64))

    assert rel_l2 < 1.0e-5, f"Error relativo L2 demasiado alto: {rel_l2}"
    assert abs_linf < 5.0e-5, f"Error absoluto Linf demasiado alto: {abs_linf}"

def test_conservation_residual_drift():
    """Verifica que la masa total se conserva con residuo menor a 1e-6 en frontera periodica."""
    N = 20_000
    phase = np.linspace(0, 2.0 * np.pi, N, dtype=np.float64)
    u_in = 10.0 + 2.0 * np.sin(phase)

    # Con viscosidad pura sin termino advectivo de choque
    u_next, _ = reference_cpu_fp64(u_in, viscosity_nu=0.1, coriolis_f=0.0, kpz_lambda=0.0)

    mass_initial = np.sum(u_in)
    mass_final = np.sum(u_next)
    relative_drift = abs(mass_final - mass_initial) / abs(mass_initial)

    assert relative_drift < 1.0e-9, f"Deriva de conservacion de masa excedida: {relative_drift}"
