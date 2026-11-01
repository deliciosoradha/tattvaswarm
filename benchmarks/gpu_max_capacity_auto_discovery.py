# ==============================================================================
# GPU MAX CAPACITY AUTO-DISCOVERY BENCHMARK (95.6 GB VRAM ROOFLINE STRESS-TEST)
# Busca dinámicamente el límite exacto de saturación de memoria y throughput
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

# Constante áurea 0x9E3779B97F4A7C15 como entero con signo de 64 bits para Triton
GOLDEN_RATIO_64 = tl.constexpr(-7046029254386353131)

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
    state = ((idx64 * stride_prime) + GOLDEN_RATIO_64) & domain_mask
    
    u_c = tl.load(u_in_ptr + offsets, mask=mask, other=0.0)
    # Operación tensorial intensiva en registros y memoria
    u_processed = u_c * 1.000001 - 0.0000005
    tl.store(u_out_ptr + offsets, u_processed, mask=mask)

    block_sum = tl.sum(tl.where(mask, u_processed, 0.0), axis=0)
    tl.store(reductions_ptr + pid, block_sum)


def run_dynamic_capacity_search():
    # Escalas de prueba progresivas hasta vaciar la VRAM de 95.6 GB
    # Memoria real (Entrada + Salida float32 = 8 bytes/nodo):
    # 500M = 3.73 GB | 1B = 7.45 GB | 5B = 37.25 GB | 10B = 74.51 GB | 12.1B = 90.15 GB
    test_scales = [
        10_000_000,       # 10M
        100_000_000,      # 100M
        500_000_000,      # 500M
        1_000_000_000,    # 1 Billion
        5_000_000_000,    # 5 Billion
        10_000_000_000,   # 10 Billion
        12_099_058_321,   # 12.1 Billion (Tope físico contiguo en 95.6 GB con 4 GB margen)
        15_000_000_000,   # 15 Billion (Requiere 111.8 GB VRAM)
        20_000_000_000,   # 20 Billion (Requiere 149.0 GB VRAM)
        22_500_000_000    # 22.5 Billion (Requiere 167.6 GB VRAM)
    ]

    BLOCK_SIZE = 2048
    results = []
    max_successful_N = 0

    print(f"{'Escala (N)':<15} | {'Memoria (GB)':<15} | {'Tiempo (ms)':<15} | {'Throughput (N/s)':<20} | {'Bw HBM (GB/s)':<15} | {'Estado'}")
    print("-" * 105)

    for N in test_scales:
        mem_gb = (N * 4 * 2) / (1024**3) # Entrada + Salida en float32 (8 bytes por nodo en memoria global)
        
        # Verificamos si cabe holgadamente dejando 4 GB de margen para el sistema y Triton
        if mem_gb > (vram_total_gb - 4.0):
            print(f"{N:<15,} | {mem_gb:<15.2f} | {'OMITIDO (Supera VRAM física)':<65}")
            continue

        try:
            torch.cuda.empty_cache()
            # Asignación directa en memoria contigua sin tensores temporales intermedios
            u_in = torch.empty(N, device=device, dtype=torch.float32).uniform_(-1.0, 1.0)
            u_out = torch.empty_like(u_in)
            
            num_blocks = triton.cdiv(N, BLOCK_SIZE)
            reds = torch.empty(num_blocks, device=device, dtype=torch.float32)

            # Warmup
            roofline_stress_kernel[(num_blocks,)](
                u_in, u_out, reds, N, 104729, BLOCK_SIZE=BLOCK_SIZE, num_warps=8
            )
            torch.cuda.synchronize()

            # Medición con eventos CUDA (promedio de 10 iteraciones para estabilidad)
            iters = 10 if N >= 1_000_000_000 else 30
            s_ev = torch.cuda.Event(enable_timing=True)
            e_ev = torch.cuda.Event(enable_timing=True)

            s_ev.record()
            for _ in range(iters):
                roofline_stress_kernel[(num_blocks,)](
                    u_in, u_out, reds, N, 104729, BLOCK_SIZE=BLOCK_SIZE, num_warps=8
                )
            e_ev.record()
            torch.cuda.synchronize()

            ms = s_ev.elapsed_time(e_ev) / iters
            throughput = N / (ms / 1000.0)
            # Bytes movidos en memoria HBM: lectura u_in (4B) + escritura u_out (4B) = 8 bytes/nodo
            bw_gbs = (N * 8 / (ms / 1000.0)) / 1e9

            print(f"{N:<15,} | {mem_gb:<15.2f} | {ms:<15.4f} | {throughput:<20,.0f} | {bw_gbs:<15.2f} | ÉXITO")
            max_successful_N = max(max_successful_N, N)

            results.append({
                "N": N,
                "memory_gb": round(mem_gb, 2),
                "latency_ms": round(ms, 4),
                "throughput_nodes_sec": round(throughput, 2),
                "effective_bandwidth_gb_s": round(bw_gbs, 2)
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
