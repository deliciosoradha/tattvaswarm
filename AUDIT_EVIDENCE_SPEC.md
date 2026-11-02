# Especificación Maestra de Auditoría y Paquete de Evidencia Forense
## Suite Científica Meru-Piṅgala & Aceleradores Triton en NVIDIA Blackwell SM120

> **Autor:** Axel Domingo Padilla Arriaga (`@deliciosoradha` / `axelpadilla98@gmail.com`)  
> **Repositorio Canónico:** [`deliciosoradha/tattvaswarm`](https://github.com/deliciosoradha/tattvaswarm)  
> **Preprints Base:** Zenodo DOIs `10.5281/zenodo.23054158` (19 pp) y `10.5281/zenodo.23871039` - `23871065`.  
> **Estándar de Evaluación:** Criterio de Auditoría de Sistemas de Supercómputo (HPC / GPU Architecture Audit).

---

## Bloque 1: Protocolo de Reproducibilidad y Harness de Un Solo Comando

### 1.1 Comando de Entrada Único
Cualquier auditor externo puede clonar el repositorio y ejecutar la suite completa de verificación mediante:

```bash
# Ejecución local o en instancia de GPU en la nube
git clone https://github.com/deliciosoradha/tattvaswarm.git
cd tattvaswarm
uv sync --frozen
uv run python benchmarks/audit_rigorous_harness.py --mode full --runs 100 --warmup 20
```

Para entornos contenerizados aislados (Docker / Podman):
```bash
docker run --gpus all --rm -v $(pwd):/workspace -w /workspace \
  ghcr.io/astral-sh/uv:python3.11-bookworm-slim \
  bash -c "uv sync --frozen && uv run python benchmarks/audit_rigorous_harness.py --mode full"
```

### 1.2 Especificación Exacta de Entorno de Hardware y Software
Las mediciones reportadas en los papers se obtienen bajo las siguientes especificaciones inmutables:
- **Arquitectura GPU:** NVIDIA Blackwell (Compute Capability `sm_120`), o fallback verificado en NVIDIA Hopper (`sm_90a`) / Ampere A100 (`sm_80`).
- **Memoria de GPU:** HBM3e (ancho de banda teórico de 8.0 TB/s en GB200; 3.35 TB/s en H100 SXM5).
- **Fijación de Relojes de Hardware:** Relojes de cómputo y memoria fijados antes de cada corrida para eliminar ruido por escalado de frecuencia DVFS:
  ```bash
  sudo nvidia-smi -pm 1
  sudo nvidia-smi -lgc 1800,1800
  ```
- **Driver NVIDIA:** `>= 560.35.03`
- **CUDA Toolkit:** `12.6 Update 2` / `12.8`
- **Compilador Triton:** `triton >= 3.0.0`
- **PyTorch:** `2.5.1+cu124` o `2.6.0`
- **Precisión Aritmética:** FP32 nativo para evolución temporal; acumulación de reducción en FP64 (`tl.float64`) para sumas globales de energía/enstrofía; referencia de validación en CPU FP64 puro.

### 1.3 Metodología de Medición Estadística Rigurosa
- **Warmup:** Mínimo 20 iteraciones no registradas para cebado de caché de instrucciones, carga de constantes y compilación JIT.
- **Número de corridas registradas:** $N = 100$ ejecuciones consecutivas.
- **Sincronización:** Uso estricto de pares `torch.cuda.Event(enable_timing=True)` alrededor de los kernels; llamadas a `torch.cuda.synchronize()` antes y después de cada evento.
- **Métricas reportadas:**
  - Media aritmética ($\mu$)
  - Mediana ($p50$)
  - Percentil 5 ($p5$) y Percentil 95 ($p95$)
  - Desviación estándar ($\sigma$)
  - Rango intercuartílico (IQR)

---

## Bloque 2: Perfilado de Microarquitectura y Trazas Nsight

### 2.1 Archivos Binarios Crudos Nsight Compute (`.ncu-rep`)
El repositorio almacena los perfiles binarios crudos sin procesar generados por `ncu` en `benchmarks/profiles/`:
```bash
ncu --target-processes all \
    --metrics gpu__time_duration.sum,dram__bytes_read.sum,dram__bytes_write.sum,lts__t_sectors.avg.pct_of_peak_sustained_elapsed,launch__occupancy_per_active_sm \
    --export benchmarks/profiles/earth2_fused_kernel.ncu-rep \
    uv run python benchmarks/nsight_earth2_cupti_trace.py
```

### 2.2 Verificación de Asignación de Registros y Cero Spills
La ausencia de derrames de registros a memoria local lenta (local memory spill = 0) se verifica directamente inspeccionando la salida de compilación de PTXAS en Triton:
```bash
TRITON_PRINT_AUTOTUNING=1 TRITON_PTXAS_OPTIONS="-v" uv run python benchmarks/audit_rigorous_harness.py
```
- **Límite objetivo por hilo:** $\le 40$ registros de 32 bits por hilo (`sm_120`), asegurando residencia completa en el archivo de registros del Streaming Multiprocessor (SM).
- **Memoria Local:** `0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads`.

### 2.3 Curva de Barrido L2 vs DRAM (Transición de Caché)
El ancho de banda efectivo no es un número plano; depende críticamente de si los datos caben en la caché L2 de la GPU (e.g., 50 MB en H100, 128 MB en Blackwell) o si saturan la HBM3e externa.
El harness ejecuta un barrido logarítmico desde $N = 10^5$ hasta $N = 10^8$ elementos:
- **Zona L2 ($N \le 10^6$):** El ancho de banda medido refleja la velocidad de la caché L2 ($\approx 8 - 12\text{ TB/s}$).
- **Zona de Transición ($10^6 < N < 10^7$):** Caída por fallos de caché hacia la controladora HBM.
- **Zona de Saturación DRAM ($N \ge 10^7$):** El ancho de banda converge asíntóticamente al ancho de banda sostenido de HBM3e ($2,500 - 3,000\text{ GB/s}$ en problemas streaming matrix-free).

---

## Bloque 3: Baselines Justas y Desglose de Speedup

### 3.1 Comparativa Trilateral Obligatoria
Cualquier comparación que únicamente enfrente a Triton contra PyTorch Eager (`torch.roll`) es metodológicamente engañosa, ya que `torch.roll` crea copias temporales completas en memoria global.
Por lo tanto, la suite de auditoría evalúa tres baselines idénticas con el mismo tensor de entrada y misma semilla:

$$\text{Speedup Real} = \frac{T(\text{torch.compile max-autotune})}{T(\text{Triton Fused Kernel})}$$

1. **Baseline 1: PyTorch Eager (Sin Fusión)**
   - Operadores convencionales (`torch.roll`, adición, multiplicación elemental).
   - Genera múltiples kernels CUDA independientes con sincronización intermedia en VRAM.
2. **Baseline 2: `torch.compile(mode="max-autotune")` con CUDA Graphs**
   - El compilador TorchDynamo + Triton Inductor genera fusión automática de bucles punto a punto y captura el grafo de ejecución eliminando sobrecarga del CPU host.
3. **Baseline 3: Triton Fused Kernel (Nuestro Enfoque)**
   - Fusión manual en registros, indexación combinatoria de Piṅgala con operadores bitwise SWAR directamente embebidos, y cálculo libre de memoria global intermedia.

### 3.2 Desglose de Atribución del Rendimiento
| Componente de Aceleración | Mecanismo Físico | Capturable por `torch.compile`? |
|---|---|---|
| Fusión de esténciles punto a punto | Eliminación de pasadas intermedias a HBM3e | **SÍ** (Inductor lo resuelve) |
| Captura de sobrecarga de lanzamiento | Eliminación de latencia del driver CPU ($\sim 10\ \mu\text{s}$) | **SÍ** (CUDA Graphs) |
| Indexación combinatoria en registros | Sustitución de matrices de adyacencia por popcount SWAR | **NO** (Requiere diseño algorítmico específico) |
| Reutilización extrema de registros en SM | Reducción de presión de registros de 64 a 32 registros | **PARCIAL** (Triton a mano supera al autotuning genérico) |

---

## Bloque 4: Validación y Corrección Numérica FP64

### 4.1 Implementación de Referencia en CPU (NumPy FP64)
Para garantizar que la velocidad no sacrifica la exactitud matemática, el harness implementa una versión espejo en FP64 que corre en CPU sin aproximaciones de precisión:
- Se evalúa la solución de referencia $u_{\text{ref}} \in \mathbb{R}^N$ en doble precisión IEEE-754.
- Se compara contra la salida del kernel Triton en FP32 promocionada a FP64: $u_{\text{gpu}} \in \mathbb{R}^N$.

### 4.2 Normas de Error Rigurosas
La tolerancia de aceptación para el pipeline de CI/CD está delimitada por:
- **Error Relativo $L_2$:**
  $$\epsilon_{L_2} = \frac{\| u_{\text{gpu}} - u_{\text{ref}} \|_2}{\| u_{\text{ref}} \|_2} \le 1.0 \times 10^{-5}$$
- **Error Máximo Absoluto $L_\infty$:**
  $$\epsilon_{L_\infty} = \max_{i} |u_{\text{gpu}}[i] - u_{\text{ref}}[i]| \le 5.0 \times 10^{-5}$$

### 4.3 Monitoreo del Residuo de Conservación
Para invariantes físicas (como conservación de masa y enstrofía):
- Se define la cantidad conservada $C(t) = \sum_{i=1}^N u[i]$.
- Se mide la deriva de conservación a lo largo de $K$ pasos de tiempo:
  $$\Delta C = \left| \frac{C(t_K) - C(t_0)}{C(t_0)} \right|$$
- En esquemas telescópicos cerrados, $\Delta C \le 10^{-6}$ por paso de tiempo bajo aritmética FP32.

---

## Bloque 5: Validación Física y Claridad Conceptual

### 5.1 Anatomía Real del Paper 1: ¿Qué son las "100 Billion Entidades"?
> [!IMPORTANT]
> **Claridad de Arquitectura:** En el Paper 1, **NO** se asignan 100 mil millones de nodos como estructuras en memoria VRAM (lo cual requeriría $>800\text{ GB}$ de HBM).
> El diseño es estrictamente **Matrix-Free y Procedural**.

- **Definición de Entidad:** Una entidad es un estado dinámico local definido por un índice global de 64 bits $i \in [0, 10^{11})$.
- **Trabajo de Cómputo por Entidad:**
  - Mapeo de Gray code: $u_c = (i \cdot p) \oplus ((i \cdot p) \gg 1)$.
  - 12 operaciones bitwise SWAR para cálculo de peso de Hamming en registros (estrato de Piṅgala).
  - 3 llamadas a funciones trascendentales sinusoidales en hardware (SFU).
  - 1 operador diferencial laplaciano + término advectivo no lineal tipo Burgers.
  - Total: **$\approx 48$ operaciones de punto flotante y lógica (FLOPs/IOPs)** por entidad.
- **Rendimiento Efectivo:** Evaluar $7.1 \times 10^8$ entidades/segundo equivale a un throughput continuo de $\approx 34\text{ GFLOPS}$ de cómputo lógico-aritmético puro en registros, con consumo cero de ancho de banda de red o DRAM de grafo.

### 5.2 Validación de Taylor-Green contra Datos DNS Canónicos
Para el Paper 5, la evolución de la tasa de disipación de energía cinética:
$$\epsilon(t) = -\frac{dK}{dt} = 2 \nu \Omega(t)$$
se calibra contra los datos de simulación numérica directa (DNS) canónicos de **Brachet et al. (1983)** y **Drikakis et al. (2007)** en el intervalo de tiempo adimensional $t \in [0, 10]$, validando el pico de disipación turbulenta en $t \approx 9.0$.

### 5.3 Caracterización del Dataset de DeFi Sentinel (Paper 3)
- Las $10.8\text{M}$ de piscinas utilizadas en los benchmarks de estrés corresponden a una **malla sintética estandarizada** calibrada con la distribución empírica de volúmenes de Uniswap v3 y Curve Finance.
- La latencia reportada ($\le 80\ \mu\text{s}$) es **latencia de cómputo puro del kernel en GPU**. No incluye el retardo de serialización RPC de nodo Ethereum/Arbitrum ($\approx 15 - 50\text{ ms}$) ni la propagación de mempool P2P.

---

## Bloque 6: Modos de Falla y Límites del Método (Anti-Fragilidad)

Un reporte creíble delimita explícitamente dónde la técnica deja de ser aplicable:

1. **Topologías de Grafo No Uniformes:** La estratificación binomial de Meru-Piṅgala asume simetría combinatoria basada en hipercubos $Q_n$. En grafos biológicos o redes libres de escala con coeficientes de agrupamiento asimétricos masivos (distribución de ley de potencia extrema), la asignación estática a estratos de Hamming produce desbalance de carga entre warps de la GPU.
2. **Mallas Lagrangianas Desestructuradas:** La formulación matrix-free requiere indexación implícita de vecinos contiguos. En elementos finitos no estructurados con reconexión de malla continua, el costo de indirección de punteros anula la ganancia de la fusión en registros.
3. **Regímenes Dominados por Multiplicación de Matrices Densa (Compute-Bound):** Si el problema consiste en GEMMs densos donde los Tensor Cores operan al 95% de saturación de cómputo, este esquema de esténciles y fusión diferencial no ofrece ventaja frente a bibliotecas hiper-optimizadas como CUTLASS o cuBLAS.

---

## Bloque 7: Trazabilidad, Gobernanza y Hoja de Ruta Upstream

### 7.1 Procedencia de Código y Git
- Commits atómicos fechados secuencialmente en [`deliciosoradha/lab-master`](https://github.com/deliciosoradha/lab-master) y [`deliciosoradha/tattvaswarm`](https://github.com/deliciosoradha/tattvaswarm).
- Uso de herramientas de IA: Se divulga abiertamente que las herramientas LLM se emplean como asistentes de aceleración sintáctica y scaffolding de tests, mientras que la derivación matemática, las ecuaciones de conservación y la arquitectura de hardware corresponden al autor humano.

### 7.2 Hoja de Ruta para Contribución Upstream (Terceros)
Para cerrar el vacío de validación por terceros, el plan de contribución técnica contempla:
1. **Pull Request en `openai/triton`:** Aportar el operador optimizado de conteo de bits SWAR / gray-code mapping como un patrón de microarquitectura para generación de índices en Triton.
2. **Reproducción Abierta:** Instancias reproducibles en Google Colab Pro / Nebius Cloud para que cualquier revisor ejecute `audit_rigorous_harness.py` en hardware independiente.
