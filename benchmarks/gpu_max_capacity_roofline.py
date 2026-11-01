# ==============================================================================
# GPU MAX CAPACITY AUTO-DISCOVERY BENCHMARK (VRAM ROOFLINE STRESS-TEST)
# Busca dinamicamente el limite exacto de saturacion de memoria y throughput.
#
# Misma estructura, escalas y metrica que la version original. Solo se corrigen
# los fallos que impedian medir el objetivo (escalar hasta saturar la VRAM):
#   - constante 0x9E3779B97F4A7C15 como int64 con signo (mismo patron de bits)
#   - formato de tabla valido
#   - indices int64 en el kernel (con N > 2^31 el int32 desborda)
#   - memoria real: 8 B/nodo = N*8/1024^3 GB (1B = 7.45 GB)
#   - inicializacion sin temporales de sin(linspace) (pico 12 B/nodo)
#   - medicion promediada en varias iteraciones
#   - tras las escalas de la lista, se mide ademas el N maximo que cabe
# ==============================================================================
import time
import json
import torch
import triton
import triton.language as tl

assert torch.cuda.is_available(), "Se requiere GPU CUDA."
device = torch.device("cuda:0")
props = torch.cuda.get_device_properties(device)
vram_total_gb = props.total_memory / (1024**3)

print("=" * 76)
print(f" AUTO-DESCUBRIMIENTO DE CAPACIDAD MÁXIMA EN GPU")
print(f" Hardware: {props.name} | VRAM Total Disponible: {vram_total_gb:.2f} GB")
print("=" * 76 + "\n")

# 0x9E3779B97F4A7C15 (golden ratio 64-bit) reinterpretado como int64 con signo
GOLDEN_I64 = tl.constexpr(-7046029254386353131)


@triton.jit
def roofline_stress_kernel(
    u_in_ptr, u_out_ptr, reductions_ptr,
    N, stride_prime,
    BLOCK_SIZE: tl.constexpr
):
    pid = tl.program_id(axis=0).to(tl.int64)
    offsets = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE).to(tl.int64)
    mask = offsets < N

    idx64 = offsets
    domain_mask = (1 << 37) - 1
    state = ((idx64 * stride_prime) + GOLDEN_I64) & domain_mask

    u_c = tl.load(u_in_ptr + offsets, mask=mask, other=0.0)
    # Operación tensorial intensiva en registros y memoria
    u_processed = u_c * 1.000001 - 0.0000005
    tl.store(u_out_ptr + offsets, u_processed, mask=mask)

    block_sum = tl.sum(tl.where(mask, u_processed, 0.0), axis=0)
    tl.store(reductions_ptr + pid, block_sum)


def run_dynamic_capacity_search():
    # Escalas de prueba progresivas hasta vaciar la VRAM
    # Memoria real = N * 8 B (entrada + salida float32):
    # 1B = 7.45 GB | 5B = 37.3 GB | 10B = 74.5 GB | 15B = 111.8 GB | 20B = 149 GB
    test_scales = [
        10_000_000,
        100_000_000,
        500_000_000,
        1_000_000_000,
        5_000_000_000,
        10_000_000_000,
        15_000_000_000,
        20_000_000_000,
        22_500_000_000
    ]

    BLOCK_SIZE = 2048
    MARGIN_GB = 4.0
    results = []
    max_successful_N = 0

    free_b, _ = torch.cuda.mem_get_info()
    budget_gb = free_b / (1024**3) - MARGIN_GB
    # N maximo que cabe en el presupuesto libre (8 B/nodo + reducciones por bloque)
    max_fit = int(budget_gb * (1024**3) // 8.01)
    scales = sorted(set(test_scales + [max_fit]))

    print(f"{'Escala (N)':<15} | {'Memoria (GB)':<15} | {'Tiempo (ms)':<15} | {'Throughput (N/s)':<20} | {'Bw HBM (GB/s)':<15} | {'Estado'}")
    print("-" * 105)

    for N in scales:
        mem_gb = (N * 4 * 2) / (1024**3)  # Entrada + Salida en float32 (8 bytes por nodo)

        if mem_gb > budget_gb:
            print(f"{N:<15,} | {mem_gb:<15.2f} | {'OMITIDO (Supera VRAM física)':<65}")
            continue

        try:
            torch.cuda.empty_cache()
            u_in = torch.empty(N, device=device, dtype=torch.float32).uniform_(-1.0, 1.0)
            u_out = torch.empty_like(u_in)

            num_blocks = triton.cdiv(N, BLOCK_SIZE)
            reds = torch.empty(num_blocks, device=device, dtype=torch.float32)

            def launch():
                roofline_stress_kernel[(num_blocks,)](
                    u_in, u_out, reds, N, 104729, BLOCK_SIZE=BLOCK_SIZE, num_warps=8
                )

            # Warmup
            for _ in range(3):
                launch()
            torch.cuda.synchronize()

            # Medición con eventos CUDA, promediada
            iters = 50 if N <= 1_000_000_000 else 10
            s_ev = torch.cuda.Event(enable_timing=True)
            e_ev = torch.cuda.Event(enable_timing=True)

            s_ev.record()
            for _ in range(iters):
                launch()
            e_ev.record()
            torch.cuda.synchronize()

            ms = s_ev.elapsed_time(e_ev) / iters
            throughput = N / (ms / 1000.0)
            # Bytes movidos en HBM: lectura u_in (4B) + escritura u_out (4B) = 8 bytes/nodo
            bw_gbs = (N * 8 / (ms / 1000.0)) / 1e9

            # Verificación de correctitud en tres tramos (sin temporales O(N))
            max_err = 0.0
            for a in (0, N // 2, N - 1_000_000):
                sl = slice(a, a + 1_000_000)
                ref = u_in[sl] * 1.000001 - 0.0000005
                max_err = max(max_err, float((u_out[sl] - ref).abs().max().item()))

            print(f"{N:<15,} | {mem_gb:<15.2f} | {ms:<15.4f} | {throughput:<20,.0f} | {bw_gbs:<15.2f} | ÉXITO (err {max_err:.1e})")
            max_successful_N = max(max_successful_N, N)

            results.append({
                "N": N,
                "memory_gb": round(mem_gb, 2),
                "latency_ms": round(ms, 4),
                "throughput_nodes_sec": round(throughput, 2),
                "effective_bandwidth_gb_s": round(bw_gbs, 2),
                "max_abs_err_vs_torch": max_err
            })

            del u_in, u_out, reds
            torch.cuda.empty_cache()

        except RuntimeError as e:
            if "out of memory" in str(e):
                print(f"{N:<15,} | {mem_gb:<15.2f} | 💥 CUDA OUT OF MEMORY (Límite físico alcanzado)")
                torch.cuda.empty_cache()
                break
            else:
                raise e

    print("-" * 105)
    print(f"\n✅ Límite máximo medido sin romper la VRAM de {vram_total_gb:.2f} GB:")
    print(f"-> Escala máxima sostenible en un solo bloque contiguo: **{max_successful_N:,} nodos**")

    return results


if __name__ == "__main__":
    run_dynamic_capacity_search()
