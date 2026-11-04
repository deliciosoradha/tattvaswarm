# Hermes Kanban — Tattva Swarm × Shiva Router

## Sprint final hackathon (cierre Nov 4, 9 PM EST)

| ID | Estado | Tarea | DoD / dueño |
| :--- | :--- | :--- | :--- |
| META-01 | IN_PROGRESS | Créditos + Spend Limit $100 | Portal Meta/Baseten/Modal — usuario |
| META-02 | READY | Push `meta_hackathon_2026/` a GitHub | `push_to_github.sh` listo — usuario ejecuta (auth propia) |
| META-03 | LOCAL_OK | Corrida budget $100/$50 | `logs/meta_credit_ledger.json` ≤ $100 + $50 reserva — corrida full con APIs reales: usuario |
| META-04 | DONE | Paper PDF vía Tectonic | `meta_hackathon_2026/paper_shiva_muse_verification.pdf` (81K, sin errores) |
| META-05 | TODO | Video demo ≤ 3:00 | Guion en `DEMO_SCRIPT.md` — usuario graba/publica |
| META-06 | TODO | Envío portal Cerebral Valley | Usuario, antes del cierre |

## Backlog post-hackathon (independiente del submission)

### POST-01 — Endpoint de investigación genérico con gate x402 + MPP
- **Scope:** endpoint que ofrezca investigaciones arbitrarias sobre
  Tattva-Swarm + Shiva Router + Meru-Pingala, fuera del hackathon.
- **Gate x402:** endpoint cobra USDC por llamada (HTTP 402, esquema exact/EIP-3009),
  API key/allowlist por cliente. Implementar como paid API con flow de cobro confirmado.
- **MPP (Machine Payment Protocol, vía Tempo):** lado cliente paga 402s con
  cualquier token (swap+bridge a Tempo, chain 4217) cuando el wallet Tempo
  no tiene saldo. Toda tx requiere confirmación explícita del usuario.
- **Prerrequisito:** antes de implementar, cargar skills de pago (cobro x402
  lado servidor + pago 402/MPP lado cliente) y seguir sus gates de confirmación.
- **Dependency:** arranca solo tras cerrar META-01–META-06.
- **DoD:** endpoint vivo + 1 job real de prueba + doc de precios/límites.
- **Estado:** QUEUED — no implementar en este sprint.

### POST-02 — Ronda masiva swarm en Colab (colab-cli + G4) + Atman gate (Rust)
- **Scope:** ronda masiva de agentes investigadores sobre Tattva-Swarm /
  Shiva / Meru vía Colab MCP con colab-cli en GPU G4. Gate Atman en Rust
  como filtro inteligente (no brute force) + medición de hardware al 100%.
- **Recon local:** cargo/rustc 1.99.0 OK (gate compilable en CPU);
  colab-cli ausente (instalar); sin GPU local (nvidia-smi ausente).
- **Por confirmar:** GPU "G4" exacta (¿tier Colab/RunPod/L4?), auth de Colab,
  presupuesto del run. Sin GPU provisionada sin costo confirmado.
- **Dependency:** tras cierre META; coordinar orden con POST-01.
- **DoD:** N agentes en G4, tasa hallazgo vs brute force, % uso GPU/VRAM,
  ledger de costos del run.
- **Workload diana:** `lab-master/scripts/colab_cybersec_benchmark_runner.py`
  (30 escenarios red/blue-team, 5 categorías; exige CUDA — verificado que
  aborta sin GPU/torch local; corrida completa solo en G4).
- **Evidencia 2026-11-03 (parcial):** Colab MCP (127.0.0.1:9223,
  ColabMCP 2.14.5) conectado; runtime GPU confirmado por celda real:
  **NVIDIA RTX PRO 6000 Blackwell Server Edition, 188 SMs, 94.97 GiB,
  torch 2.11.0+cu130, CUDA OK**. Celda swarm ejecutada (`SWARM_CELL_OK`):
  estratificación Meru-Piṅgala Q_14 balanceada, despacho kanban por
  paridad con certificados SHA-256, matmul 8192² ×10 = 75.8 TFLOPS.
  Inferencia Muse Spark/Glimmer en vivo: **bloqueada** — no hay claves
  Meta/Baseten en `~/.env` (META-01). Benchmark red/blue de 30
  escenarios: pendiente de subir el runner al notebook.
- **Estado:** IN_PROGRESS (workload base corrido; falta inferencia Meta
  real y benchmark completo).

### POST-03 — Launch onchain x402 + proxy MPP (service token por feature)
- **Scope:** servicio con token por feature para optimizar calls; adapters
  para cualquier coder; suite de 10 benchmarks reales con Hermes/agy +
  Meta Muse (best model o default config); docs + paper + post social vía
  MCPs; configurar todo.
- **Gates obligatorios (sin excepción):** (1) ninguna tx onchain sin
  confirmación explícita previa (monto, token, destino, gas); (2) ningún
  post social sin texto aprobado por ti; (3) ninguna provisión con costo
  sin confirmar.
- **Seller path x402:** Circle Gateway Nanopayments por defecto (proxy
  Express con middleware, redes desde docs/inspect en vivo sin hardcodear);
  testnet primero; marketplace como submission package, no publicación instantánea.
- **Seguridad fondos:** USDC irreversible — `--estimate` primero,
  `--max-amount` ceñido al precio, buyer wallet solo como harness final.
- **Por definir:** las 10 tareas benchmark, chain + wallet + presupuesto,
  coders objetivo de los adapters, red social y MCP a usar.
- **Dependency:** tras cierre META; coordinar con POST-01/02.
- **Estado:** QUEUED — no lanzar sin tus confirmaciones.
- **Sub-tarea medición de fuentes (`til_network`/`fdtd_phaseop`):**
  `SKIPPED_MISSING_SOURCE` — búsqueda ampliada
  `find /home/delideli -maxdepth 5` (incluye `~/lab-master` y
  `~/Documentos/3333`) sin ningún resultado (2026-11-03). Hipótesis:
  backups en Drive (rclone `gdrive:`) / Linode o instancia mcphub/cpu.
  Auditoría de DBs grandes en Drive en curso. Reabrir solo si las
  fuentes aparecen; sin fuentes no se calcula ningún delta.

### POST-04 — hello-os + HK-1 sincronizados a lab-master
- **DONE 2026-11-03:** commit `7caca29` (push OK) en
  `lab-master/reports/hello_hk1_20261103/`: `hello_os/` (11 archivos,
  testbench iverilog 3/0), bundle HK-1 íntegro (SHA256SUMS 7/7 OK) y
  reporte de síntesis corregido — Yosys 0.52 = **4,268 celdas**, sim
  HK-1 PASS con 6,667 checks. La cifra previa de 7,810 celdas queda
  retractada (ruta inexistente). Rama del hackathon intacta.

## SUBMIT — Paquete de envíos (preparado 2026-11-03)

### SUBMIT-01 — Zenodo (paper forense Samsara)
- **Artefactos:** `lab-master/reports/samsara_forensic_20261103/`
  (`INFORME_FORENSE_SAMSARA_20261103.md`, `paper_samsara_forensic.pdf`,
  `PLAN_RELANZAMIENTO.md`), commits `88b99e2` + `9c77df3` pusheados.
- **DoD:** subir PDF a Zenodo (nuevo registro o versión), obtener DOI,
  pegar DOI en README de lab-master y en este kanban.
- **Bloqueo:** requiere tu sesión/token Zenodo. No ejecuto sin que lo abras tú.
- **Estado:** READY (artefactos listos; falta tu login).

### SUBMIT-02 — Cerebral Valley (Meta Global AI Developer Hackathon)
- **Campos pre-llenados:** ver `SUBMISSION_FORM.md` en la raíz del repo.
- **DoD:** formulario enviado antes de Nov 4, 9:00 PM EST + screenshot de
  confirmación guardado en `session/`.
- **Bloqueos:** META-01 (claves/créditos), META-05 (video ≤3:00). El envío
  sin inferencia en vivo verificable pierde el premio Open Weights ($10K);
  enviar igual por track principal si el video está.
- **Estado:** READY-WITH-BLOCKERS.

### SUBMIT-03 — Hugging Face (bucket de artefactos)
- **Contenido:** paper Shiva-Muse (PDF), dataset sintético Samsara
  (cuando exista, Fase A del plan), tarjeta de dataset con procedencia.
- **DoD:** repo HF público con `README.md` (dataset card) + archivos.
- **Credencial:** `HF_TOKEN` presente en `~/.env` (verificado por nombre;
  nunca impreso). La subida la disparo solo con tu OK.
- **Estado:** READY (falta tu OK para subir).

### DOC-01 — Wiki del proyecto
- **Artefactos:** carpeta `wiki/` (Home, Arquitectura, Forense-Samsara,
  Reproducibilidad) versionada en el repo y enlazada desde README.
- **DoD:** `wiki/Home.md` + 3 páginas, enlazadas y pusheadas.
- **Estado:** IN_PROGRESS.

### AUDIT-E2E — Auditoría extremo a extremo del hackathon
- **Artefacto:** `auditor_estricto_meta.py` (raíz) ejecutado; veredicto
  registrado en este kanban y en `session/`.
- **DoD:** script corre limpio y su salida queda en el repo; los fallos
  por claves (META-01) se documentan como bloqueos del usuario, no se
  maquillan.
- **Estado:** IN_PROGRESS.

### COLAB-DATA — Dataset sintético + LoRA + RL (Colab GPU)
- **Plan:** `lab-master/reports/samsara_forensic_20261103/PLAN_RELANZAMIENTO.md` §3
  (Fase A dataset/Data Designer → Fase B LoRA PEFT → Fase C RL GRPO/DPO
  sobre replay, todo en Colab GPU Blackwell ya conectada).
- **DoD fase A:** script `samsara_synthetic_funding.py` con
  `load_config_builder()` + muestra generada en Colab (100k filas).
- **Gates:** sin claves Meta no hay juez LLM en vivo; el host local no
  corre nada pesado (orden del usuario).
- **Estado:** QUEUED (diseño listo en el plan; ejecutar en Colab).
