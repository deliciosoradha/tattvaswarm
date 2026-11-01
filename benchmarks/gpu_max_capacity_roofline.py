# ==============================================================================
# GPU MAX CAPACITY AUTO-DISCOVERY BENCHMARK (roofline / VRAM saturation)
# Busca el limite de memoria y el throughput sostenido de un kernel
# memory-bound (lectura 4 B + escritura 4 B por nodo).
# Correcciones respecto a la version original: formato de tabla valido,
# indices int64 (N > 2^31), contabilidad real de memoria, inicializacion sin
# temporales, medicion promediada sobre varias iteraciones.
# ==============================================================================
import json
import torch
import triton
import triton.language as tl

assert torch.cuda.is_available(), "Se requiere GPU CUDA."
device = torch.device("cuda:0")
props = torch.cuda.get_device_properties(device)
vram_total_gb = props.total_memory / (1024 ** 3)


@triton.jit
def roofline_stress_kernel(u_in_ptr, u_out_ptr, reductions_ptr, N,
                           BLOCK_SIZE: tl.constexpr):
    pid = tl.program_id(axis=0).to(tl.int64)
    offsets = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE).to(tl.int64)
    mask = offsets < N
    u_c = tl.load(u_in_ptr + offsets, mask=mask, other=0.0)
    u_processed = u_c * 1.000001 - 0.0000005
    tl.store(u_out_ptr + offsets, u_processed, mask=mask)
    block_sum = tl.sum(tl.where(mask, u_processed, 0.0), axis=0)
    tl.store(reductions_ptr + pid, block_sum)


BLOCK_SIZE = 2048
MARGIN_GB = 4.0


def bytes_needed(N):
    # u_in + u_out (float32) + reducciones por bloque
    return N * 8 + triton.cdiv(N, BLOCK_SIZE) * 4


def measure(N, iters):
    u_in = torch.empty(N, device=device, dtype=torch.float32).uniform_(-1.0, 1.0)
    u_out = torch.empty_like(u_in)
    num_blocks = triton.cdiv(N, BLOCK_SIZE)
    reds = torch.empty(num_blocks, device=device, dtype=torch.float32)

    def launch():
        roofline_stress_kernel[(num_blocks,)](u_in, u_out, reds, N,
                                              BLOCK_SIZE=BLOCK_SIZE, num_warps=8)

    for _ in range(3):
        launch()
    torch.cuda.synchronize()
    s, e = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
    s.record()
    for _ in range(iters):
        launch()
    e.record()
    torch.cuda.synchronize()
    ms = s.elapsed_time(e) / iters
    # verificacion de correccion contra torch sobre muestras (sin temporales O(N))
    max_err = 0.0
    for a in (0, N // 2, N - 1_000_000):
        sl = slice(a, a + 1_000_000)
        ref = u_in[sl] * 1.000001 - 0.0000005
        max_err = max(max_err, float((u_out[sl] - ref).abs().max().item()))
    del u_in, u_out, reds
    return ms, max_err


def run_dynamic_capacity_search():
    free_b, total_b = torch.cuda.mem_get_info()
    budget = free_b - MARGIN_GB * (1024 ** 3)
    print("=" * 100)
    print(f" GPU: {props.name} | VRAM total {vram_total_gb:.2f} GB | libre {free_b / 1024**3:.2f} GB")
    print("=" * 100)

    scales = [10_000_000, 100_000_000, 500_000_000, 1_000_000_000,
              2_000_000_000, 5_000_000_000, 8_000_000_000, 10_000_000_000]
    max_fit = int(budget // 8.01)
    if max_fit not in scales:
        scales.append(max_fit)
    scales = sorted(set(s for s in scales if bytes_needed(s) <= budget))

    hdr = f"{'N':>16} | {'Mem GB':>8} | {'ms/iter':>10} | {'Nodos/s':>16} | {'BW GB/s':>9} | {'max_err':>9} | estado"
    print(hdr)
    print("-" * len(hdr))
    results, max_ok = [], 0
    for N in scales:
        iters = 50 if N <= 1_000_000_000 else 10
        try:
            torch.cuda.empty_cache()
            ms, err = measure(N, iters)
        except torch.OutOfMemoryError:
            print(f"{N:>16,} | {bytes_needed(N) / 1024**3:>8.2f} | OOM (limite fisico)")
            torch.cuda.empty_cache()
            break
        mem_gb = bytes_needed(N) / 1024 ** 3
        bw = (N * 8 / (ms / 1000.0)) / 1e9
        print(f"{N:>16,} | {mem_gb:>8.2f} | {ms:>10.4f} | {N / (ms / 1000.0):>16,.0f} | {bw:>9.1f} | {err:>9.2e} | OK")
        max_ok = N
        results.append({"N": N, "memory_gb": round(mem_gb, 2), "ms_per_iter": round(ms, 4),
                        "nodes_per_s": round(N / (ms / 1000.0)), "bw_gb_s": round(bw, 1),
                        "max_abs_err_vs_torch": err})
    print(f"\nN maximo medido: {max_ok:,} nodos")
    print(json.dumps({"gpu": props.name, "vram_total_gb": round(vram_total_gb, 2),
                      "max_N": max_ok, "results": results}))
    return results


if __name__ == "__main__":
    run_dynamic_capacity_search()
