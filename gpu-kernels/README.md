# GPU Kernels & HPC Engine Showcase

High-performance computing kernels spanning **Bare-Metal CUDA C++**, **OpenAI Triton GPU**, and **NVIDIA Nsight/CUPTI Hardware Telemetry**, developed for the **RadhikaChain & TattvaSwarm** ecosystems.

Tested and benchmarked on **NVIDIA RTX PRO 6000 Blackwell Server Edition (94.97 GB VRAM, 188 SMs, `sm_120`)** and **NVIDIA A100-SXM4-80GB (`sm_80`)**.

---

## 1. Native CUDA C++ Kernels (`/gpu-kernels/cuda/`)

Production CUDA kernels demonstrating fine-grained memory hierarchy control, warp-level primitives, and bank-conflict avoidance:

| Kernel | Source File | Architecture Feature | Performance Characteristics |
|---|---|---|---|
| **Tree Reduction** | [`nim_C03.cu`](cuda/nim_C03.cu) | Shared-memory logarithmic parallel reduction + atomic accumulation | Zero warp divergence on tail passes; handles up to $N=65,536$ in single-block resident SRAM. |
| **Grid-Stride Reduction** | [`nim_C04.cu`](cuda/nim_C04.cu) | Grid-stride loop with persistent thread mapping + coalesced memory access | Eliminates kernel launch overhead; scales dynamically across any SM count independent of grid dimensions. |
| **Tiled Matrix Transpose** | [`nim_C05.cu`](cuda/nim_C05.cu) | 2D shared-memory block tiling with `[TILE_DIM][TILE_DIM + 1]` padding | **100% Shared Memory Bank Conflict Elimination** (no multi-way bank conflicts across 32 banks). |

---

## 2. Triton Multiphysics & Stratified Hypercube Engines

Fused register-resident Triton kernels operating on combinatorially stratified hypercubes without global memory round-trips:

### A. Global Systemic Resilience Engine ($N = 100,000,000,000$ Nodes)
- **Source:** [`benchmarks/global_systemic_resilience_paper.py`](../benchmarks/global_systemic_resilience_paper.py)
- **Topology:** Bipartite Hypercube $Q_{36}$ ($2^{36} \approx 68.7$ Billion direct states).
- **Architecture:** 64-bit SWAR (SIMD Within A Register) popcount for Hamming stratum calculation + coupled Navier-Stokes / Burgers-KPZ shock front + Frustrated Edwards-Anderson Spin-Glass dynamics.
- **Measured Throughput:** **714,261,480 coupled entities per second**.
- **Conservation Quality:** Telescopic conservation residual of **`-1.98e-9`** across $10^{11}$ evaluations.

### B. NVIDIA Earth-2 Atmospheric Sub-Grid Closure ($N = 103,824,000$ Nodes)
- **Source:** [`benchmarks/nsight_earth2_cupti_trace.py`](../benchmarks/nsight_earth2_cupti_trace.py)
- **Problem:** Sub-grid turbulent enstrophy closure and 4D-Var adjoint operator for ERA5 spherical harmonics (100 barometric levels).
- **Speedup vs PyTorch Eager (18 kernels):** **`44.01x` Speedup** ($37.84\,\text{ms} \rightarrow 0.8597\,\text{ms}$).
- **Effective HBM Bandwidth:** **`1,449.14 GB/s`**.
- **Hardware Telemetry (PTX/SASS):** Exactly **40 registers/thread**, **`0 bytes` register spilling** to local memory, 32 B shared memory SRAM.

### C. GPU Max Capacity VRAM Saturation Benchmark
- **Source:** [`benchmarks/gpu_max_capacity_auto_discovery.py`](../benchmarks/gpu_max_capacity_auto_discovery.py)
- **Max Contiguous Scale:** **`12,099,058,321 nodes` (90.15 GB VRAM)** allocated and executed in a single contiguous pass without OOM.
- **Throughput:** Flat, sustained roofline saturation at **`1,461.48 GB/s`** across all scales from 100M to 12.1B.

---

## 3. Hardware Evidence & Telemetry Files

- **CUPTI Chrome Trace JSON:** [`docs/evidence/nsight_cupti_triton_trace.json`](../docs/evidence/nsight_cupti_triton_trace.json) (load directly in [ui.perfetto.dev](https://ui.perfetto.dev) or NVIDIA Nsight Systems).
- **Hardware Timeline Diagram:** [`docs/evidence/nsight_earth2_gpu_trace_evidence.png`](../docs/evidence/nsight_earth2_gpu_trace_evidence.png).
