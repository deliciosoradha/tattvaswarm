#!/usr/bin/env python3
"""
audit_rigorous_harness.py
Harness riguroso de auditoria cientifica y de microarquitectura para la suite
Meru-Pingala y aceleradores Triton (Blackwell SM120 / Hopper / Ampere / CPU Fallback).

Implementa:
1. Referencia CPU en FP64 puro (NumPy).
2. PyTorch Eager (con torch.roll y stencils sin fusionar).
3. PyTorch compilado: torch.compile(mode="max-autotune") con CUDA Graphs.
4. Fused Triton Kernel (registros directos y popcounts SWAR).
5. Validacion numerica: normas L2 y L_infinito relativas.
6. Metodologia estadistica rigurosa: warmup >= 10, corridas >= 100, mediana, p5, p95, stddev.
"""

import sys
import os
import time
import math
import argparse
import json
import numpy as np

# Intentar importar PyTorch y Triton
try:
    import torch
    import torch.nn.functional as F
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

try:
    import triton
    import triton.language as tl
    HAS_TRITON = True
except ImportError:
    HAS_TRITON = False


# ==============================================================================
# 1. REFERENCIA CPU EN FP64 PURO (NUMPY IEEE-754)
# ==============================================================================
def reference_cpu_fp64(u_in, n_bits=24, viscosity_nu=0.14, coriolis_f=0.001, kpz_lambda=0.06):
    """
    Calculo de referencia en doble precision FP64 en CPU.
    """
    N = len(u_in)
    u_64 = np.asarray(u_in, dtype=np.float64)

    # 1. Mapeo combinatorio de Meru-Pingala
    domain_mask = (1 << n_bits) - 1
    idx = np.arange(N, dtype=np.int64)
    gray = ((idx * 104729) & domain_mask) ^ (((idx * 104729) & domain_mask) >> 1)
    
    # Popcount vectorizado en FP64
    hamming_stratum = np.array([bin(int(g)).count('1') for g in gray], dtype=np.float64)
    baroclinic_factor = 1.0 + 0.015 * (hamming_stratum - (n_bits * 0.5))

    # 2. Estencil periodico diferencial
    u_l = np.roll(u_64, 1)
    u_r = np.roll(u_64, -1)
    laplacian = (u_l - 2.0 * u_64) + u_r
    grad_u = 0.5 * (u_r - u_l)
    subgrid_shock = -kpz_lambda * u_64 * grad_u
    coriolis_term = coriolis_f * (u_r - u_64)

    # 3. Evolucion temporal (Forecast step)
    du_dt = (viscosity_nu * baroclinic_factor * laplacian) + subgrid_shock + coriolis_term
    u_next = u_64 + du_dt

    # 4. Enstrofia
    enstrophy = np.sum(0.5 * grad_u * grad_u)
    return u_next, enstrophy


# ==============================================================================
# 2. PYTORCH EAGER BASELINE
# ==============================================================================
def pytorch_eager_baseline(u_in, n_bits=24, viscosity_nu=0.14, coriolis_f=0.001, kpz_lambda=0.06):
    domain_mask = (1 << n_bits) - 1
    N = u_in.shape[0]
    device = u_in.device

    idx64 = torch.arange(N, device=device, dtype=torch.int64)
    gray_u = ((idx64 * 104729) & domain_mask) ^ (((idx64 * 104729) & domain_mask) >> 1)
    x = gray_u.to(torch.int32)
    x = x - ((x >> 1) & 0x55555555)
    x = (x & 0x33333333) + ((x >> 2) & 0x33333333)
    hamming_stratum = (((x + (x >> 4)) & 0x0F0F0F0F) * 0x01010101) >> 24
    baroclinic_factor = 1.0 + 0.015 * (hamming_stratum.to(torch.float32) - (n_bits * 0.5))

    u_l = torch.roll(u_in, shifts=1, dims=0)
    u_r = torch.roll(u_in, shifts=-1, dims=0)
    laplacian = (u_l - 2.0 * u_in) + u_r
    grad_u = 0.5 * (u_r - u_l)
    subgrid_shock = -kpz_lambda * u_in * grad_u
    coriolis_term = coriolis_f * (u_r - u_in)

    du_dt = (viscosity_nu * baroclinic_factor * laplacian) + subgrid_shock + coriolis_term
    u_next = u_in + du_dt
    enstrophy = torch.sum(0.5 * grad_u * grad_u)
    return u_next, enstrophy


# ==============================================================================
# 3. KERNEL TRITON FUSED MATRIX-FREE
# ==============================================================================
if HAS_TRITON:
    @triton.jit
    def triton_fused_stencil_kernel(
        u_in_ptr,
        u_out_ptr,
        enstrophy_out_ptr,
        N,
        n_bits,
        viscosity_nu,
        coriolis_f,
        kpz_lambda,
        BLOCK_SIZE: tl.constexpr
    ):
        pid = tl.program_id(axis=0).to(tl.int64)
        offsets = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE).to(tl.int64)
        mask = offsets < N

        idx64 = offsets
        domain_mask = (1 << n_bits) - 1
        gray_u = ((idx64 * 104729) & domain_mask) ^ (((idx64 * 104729) & domain_mask) >> 1)
        x = gray_u.to(tl.int32)
        x = x - ((x >> 1) & 0x55555555)
        x = (x & 0x33333333) + ((x >> 2) & 0x33333333)
        hamming_stratum = (((x + (x >> 4)) & 0x0F0F0F0F) * 0x01010101) >> 24
        baroclinic_factor = 1.0 + 0.015 * (hamming_stratum.to(tl.float32) - (n_bits * 0.5))

        left_off = tl.where(offsets == 0, N - 1, offsets - 1)
        right_off = tl.where(offsets == N - 1, 0, offsets + 1)

        u_c = tl.load(u_in_ptr + offsets, mask=mask, other=0.0)
        u_l = tl.load(u_in_ptr + left_off, mask=mask, other=0.0)
        u_r = tl.load(u_in_ptr + right_off, mask=mask, other=0.0)

        laplacian = (u_l - 2.0 * u_c) + u_r
        grad_u = 0.5 * (u_r - u_l)
        subgrid_shock = -kpz_lambda * u_c * grad_u
        coriolis_term = coriolis_f * (u_r - u_c)

        du_dt = (viscosity_nu * baroclinic_factor * laplacian) + subgrid_shock + coriolis_term
        u_next = u_c + du_dt
        tl.store(u_out_ptr + offsets, u_next, mask=mask)

        local_enstrophy = 0.5 * grad_u * grad_u
        tl.store(enstrophy_out_ptr + pid, tl.sum(tl.where(mask, local_enstrophy, 0.0), axis=0))


# ==============================================================================
# 4. HARNESS DE MEDIDAS ESTADISTICAS Y VALIDACION
# ==============================================================================
def compute_metrics(latencies_ms):
    arr = np.array(latencies_ms)
    return {
        "mean_ms": float(np.mean(arr)),
        "median_ms": float(np.median(arr)),
        "p5_ms": float(np.percentile(arr, 5)),
        "p95_ms": float(np.percentile(arr, 95)),
        "std_ms": float(np.std(arr)),
        "iqr_ms": float(np.percentile(arr, 75) - np.percentile(arr, 25))
    }

def run_audit(N=1_000_000, num_runs=100, warmup_runs=20):
    print("=" * 76)
    print("   ESPECIFICACION MAESTRA DE AUDITORIA: SUITE MERU-PINGALA / BLACKWELL")
    print("=" * 76)
    print(f"[*] Tamano de problema N = {N:,} elementos")
    print(f"[*] Configuracion estadistica: {warmup_runs} warmups, {num_runs} corridas registradas")

    # 1. Generar entrada base
    np.random.seed(42)
    phase = np.linspace(0, 4.0 * np.pi, N, dtype=np.float32)
    u_np = 25.0 * np.sin(phase * 2.0) + 8.5 * np.cos(phase * 6.0)

    # 2. Referencia CPU FP64
    print("\n[*] Ejecutando referencia CPU FP64 (NumPy)...")
    t0 = time.perf_counter()
    u_ref_64, enstrophy_ref_64 = reference_cpu_fp64(u_np)
    cpu_ref_time = (time.perf_counter() - t0) * 1000.0
    print(f"    Referencia CPU FP64 completada en {cpu_ref_time:.2f} ms")
    print(f"    Enstrofia de referencia: {enstrophy_ref_64:.6e}")

    results = {
        "N": N,
        "runs": num_runs,
        "warmup": warmup_runs,
        "cpu_ref_ms": cpu_ref_time,
        "enstrophy_ref": float(enstrophy_ref_64),
        "benchmarks": {}
    }

    if not HAS_TORCH:
        print("[!] PyTorch no esta instalado en este interprete.")
        return results

    has_cuda = torch.cuda.is_available()
    device = torch.device("cuda:0" if has_cuda else "cpu")
    print(f"[*] Dispositivo de evaluacion: {device} ({torch.cuda.get_device_name(0) if has_cuda else 'CPU Host'})")

    u_torch = torch.from_numpy(u_np).to(device)

    # 3. PyTorch Eager
    print("\n[*] Evaluando PyTorch Eager...")
    for _ in range(warmup_runs):
        _ = pytorch_eager_baseline(u_torch)
    if has_cuda:
        torch.cuda.synchronize()

    eager_latencies = []
    for _ in range(num_runs):
        if has_cuda:
            start_ev = torch.cuda.Event(enable_timing=True)
            end_ev = torch.cuda.Event(enable_timing=True)
            start_ev.record()
            u_eager, _ = pytorch_eager_baseline(u_torch)
            end_ev.record()
            torch.cuda.synchronize()
            eager_latencies.append(start_ev.elapsed_time(end_ev))
        else:
            t_s = time.perf_counter()
            u_eager, _ = pytorch_eager_baseline(u_torch)
            eager_latencies.append((time.perf_counter() - t_s) * 1000.0)

    results["benchmarks"]["pytorch_eager"] = compute_metrics(eager_latencies)
    print(f"    PyTorch Eager: Mediana = {results['benchmarks']['pytorch_eager']['median_ms']:.3f} ms "
          f"(p5={results['benchmarks']['pytorch_eager']['p5_ms']:.3f}, p95={results['benchmarks']['pytorch_eager']['p95_ms']:.3f})")

    # Validacion numerica Eager vs CPU FP64
    u_eager_np = u_eager.cpu().numpy().astype(np.float64)
    l2_eager = float(np.linalg.norm(u_eager_np - u_ref_64) / np.linalg.norm(u_ref_64))
    linf_eager = float(np.max(np.abs(u_eager_np - u_ref_64)))
    results["benchmarks"]["pytorch_eager"]["l2_rel_err"] = l2_eager
    results["benchmarks"]["pytorch_eager"]["linf_abs_err"] = linf_eager
    print(f"    Precision vs FP64: L2_rel = {l2_eager:.2e}, Linf_abs = {linf_eager:.2e}")

    # 4. PyTorch Compiled (torch.compile max-autotune)
    if hasattr(torch, "compile") and has_cuda:
        print("\n[*] Evaluando PyTorch Compilado: torch.compile(mode='max-autotune')...")
        try:
            compiled_fn = torch.compile(pytorch_eager_baseline, mode="max-autotune")
            # Warmup compilacion JIT
            for _ in range(warmup_runs):
                _ = compiled_fn(u_torch)
            torch.cuda.synchronize()

            compiled_latencies = []
            for _ in range(num_runs):
                start_ev = torch.cuda.Event(enable_timing=True)
                end_ev = torch.cuda.Event(enable_timing=True)
                start_ev.record()
                u_comp, _ = compiled_fn(u_torch)
                end_ev.record()
                torch.cuda.synchronize()
                compiled_latencies.append(start_ev.elapsed_time(end_ev))

            results["benchmarks"]["torch_compile_max_autotune"] = compute_metrics(compiled_latencies)
            print(f"    torch.compile: Mediana = {results['benchmarks']['torch_compile_max_autotune']['median_ms']:.3f} ms "
                  f"(p5={results['benchmarks']['torch_compile_max_autotune']['p5_ms']:.3f}, p95={results['benchmarks']['torch_compile_max_autotune']['p95_ms']:.3f})")
        except Exception as err:
            print(f"    [!] Error al compilar con torch.compile: {err}")

    # 5. Triton Fused Kernel
    if HAS_TRITON and has_cuda:
        print("\n[*] Evaluando Triton Fused Matrix-Free Kernel...")
        BLOCK_SIZE = 1024
        num_blocks = triton.cdiv(N, BLOCK_SIZE)
        u_out = torch.empty_like(u_torch)
        enstrophy_blocks = torch.empty(num_blocks, device=device, dtype=torch.float32)

        for _ in range(warmup_runs):
            triton_fused_stencil_kernel[(num_blocks,)](
                u_torch, u_out, enstrophy_blocks,
                N, 24, 0.14, 0.001, 0.06, BLOCK_SIZE=BLOCK_SIZE
            )
        torch.cuda.synchronize()

        triton_latencies = []
        for _ in range(num_runs):
            start_ev = torch.cuda.Event(enable_timing=True)
            end_ev = torch.cuda.Event(enable_timing=True)
            start_ev.record()
            triton_fused_stencil_kernel[(num_blocks,)](
                u_torch, u_out, enstrophy_blocks,
                N, 24, 0.14, 0.001, 0.06, BLOCK_SIZE=BLOCK_SIZE
            )
            end_ev.record()
            torch.cuda.synchronize()
            triton_latencies.append(start_ev.elapsed_time(end_ev))

        results["benchmarks"]["triton_fused"] = compute_metrics(triton_latencies)
        print(f"    Triton Fused: Mediana = {results['benchmarks']['triton_fused']['median_ms']:.3f} ms "
              f"(p5={results['benchmarks']['triton_fused']['p5_ms']:.3f}, p95={results['benchmarks']['triton_fused']['p95_ms']:.3f})")

        # Validacion numerica Triton vs CPU FP64
        u_triton_np = u_out.cpu().numpy().astype(np.float64)
        l2_triton = float(np.linalg.norm(u_triton_np - u_ref_64) / np.linalg.norm(u_ref_64))
        linf_triton = float(np.max(np.abs(u_triton_np - u_ref_64)))
        results["benchmarks"]["triton_fused"]["l2_rel_err"] = l2_triton
        results["benchmarks"]["triton_fused"]["linf_abs_err"] = linf_triton
        print(f"    Precision vs FP64: L2_rel = {l2_triton:.2e}, Linf_abs = {linf_triton:.2e}")

        # Desglose de speedup honesto
        eager_med = results["benchmarks"]["pytorch_eager"]["median_ms"]
        triton_med = results["benchmarks"]["triton_fused"]["median_ms"]
        speedup_vs_eager = eager_med / triton_med
        results["speedup_vs_eager"] = speedup_vs_eager
        print(f"\n[✓] Speedup Fused Triton vs PyTorch Eager: {speedup_vs_eager:.2f}x")

        if "torch_compile_max_autotune" in results["benchmarks"]:
            comp_med = results["benchmarks"]["torch_compile_max_autotune"]["median_ms"]
            speedup_vs_compile = comp_med / triton_med
            results["speedup_vs_compile"] = speedup_vs_compile
            print(f"[✓] Speedup Fused Triton vs torch.compile: {speedup_vs_compile:.2f}x")

    # Guardar reporte de auditoria en JSON
    out_dir = os.path.expanduser("~/lab-master/reports/audit")
    os.makedirs(out_dir, exist_ok=True)
    out_json = os.path.join(out_dir, f"audit_benchmark_N{N}.json")
    with open(out_json, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[✓] Reporte completo de auditoria guardado en: {out_json}")
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Harness Riguroso de Auditoria HPC")
    parser.add_argument("--N", type=int, default=1_000_000, help="Numero de elementos")
    parser.add_argument("--runs", type=int, default=100, help="Numero de corridas registradas")
    parser.add_argument("--warmup", type=int, default=20, help="Numero de corridas de warmup")
    args = parser.parse_args()

    run_audit(N=args.N, num_runs=args.runs, warmup_runs=args.warmup)
