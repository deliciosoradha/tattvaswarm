# Hermes Kanban — Tattva Swarm × Shiva Router

## Sprint final hackathon (cierre Nov 4, 9 PM EST)

| ID | Estado | Tarea | DoD / dueño |
| :--- | :--- | :--- | :--- |
| META-01 | DONE | Créditos + Spend Limit $100 | 7 llamadas reales verificadas (5 Meta API + 2 Baseten `meta-models/muse-spark-open`) en `verified_partner_inference_trace.jsonl` |
| META-02 | DONE | Push `meta_hackathon_2026/` + integración `tattva_swarm` y `muse resume 01a1c1c5-0154-7250-8767-f4beaff19eae` | Paquete unificado `src/tattva_swarm/` + `meta_hackathon_2026/` + `muse_session_bridge.py` |
| META-03 | DONE | Corrida budget $100/$50 | `logs/meta_credit_ledger.json` y `verified_partner_inference_trace.jsonl` ($0.024 usados ≤ $100.00 + $50.00 reserva intacta) |
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
- **Evidencia 2026-11-03..05:** Colab MCP (127.0.0.1:9223,
  ColabMCP 2.14.5) conectado; runtime GPU confirmado por celda real:
  **NVIDIA RTX PRO 6000 Blackwell Server Edition, 188 SMs, 94.97 GiB,
  torch 2.11.0+cu130, CUDA OK**. Celda swarm ejecutada (`SWARM_CELL_OK`):
  estratificación Meru-Piṅgala Q_14 balanceada, despacho kanban por
  paridad con certificados SHA-256, matmul 8192² ×10 = 75.8 TFLOPS.
  Benchmark red/blue de 30 escenarios ejecutado (`RB_REAL_OK`, 15 pass / 15 veto).
  Inferencia Muse Spark + Muse Spark Open en vivo completada (7 llamadas reales verificadas).
- **Estado:** DONE (workload base, Red/Blue 30 y trazas Meta/Baseten verificadas).

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
- **Campos pre-llenados:** ver [SUBMISSION_FORM.md](SUBMISSION_FORM.md) en la raíz del repo.
- **DoD:** formulario enviado antes de Nov 4, 9:00 PM EST + screenshot de
  confirmación guardado en `session/`.
- **Bloqueos:** META-05 (video ≤3:00). Inferencia en vivo verificable (`META-01` / `META-03`) ya completada con 7 `request_id` reales (elegible para premio Open Weights $10K).
- **Estado:** READY (solo falta video del usuario y envío en portal).

### SUBMIT-03 — Hugging Face (bucket de artefactos)
- **Contenido:** paper Shiva-Muse (PDF), dataset sintético Samsara
  (cuando exista, Fase A del plan), tarjeta de dataset con procedencia.
- **DoD:** repo HF público con `README.md` (dataset card) + archivos.
- **Credencial:** `HF_TOKEN` presente en `~/.env` (verificado por nombre;
  nunca impreso). La subida la disparo solo con tu OK.
- **Estado:** READY (falta tu OK para subir).

### DOC-01 — Wiki del proyecto
- **Artefactos:** carpeta `wiki/` ([Home.md](wiki/Home.md), [Arquitectura.md](wiki/Arquitectura.md), [Ashta-Gate-y-Sensor-XDP.md](wiki/Ashta-Gate-y-Sensor-XDP.md), [Forense-Samsara.md](wiki/Forense-Samsara.md), [Reproducibilidad.md](wiki/Reproducibilidad.md)) versionada en el repo y enlazada desde [README.md](README.md) y [wiki/Home.md](wiki/Home.md).
- **DoD:** `wiki/Home.md` + 4 páginas, enlazadas y sincronizadas.
- **Estado:** DONE.

### AUDIT-E2E — Auditoría extremo a extremo del hackathon
- **Artefacto:** `auditor_estricto_meta.py` (raíz) ejecutado; veredicto registrado en este kanban y en [session/20261103_143716/session_state.md](session/20261103_143716/session_state.md).
- **DoD:** `python3 auditor_estricto_meta.py .` devuelve `VEREDICTO: APROBADO.` (exit code 0: `$0.02 usados | $50.00 reserva`, `Llamadas open-weight verificadas: 2`, 7 llamadas totales sincronizadas en `logs/verified_partner_inference_trace.jsonl` y `meta_hackathon_2026/logs/verified_partner_inference_trace.jsonl`).
- **Estado:** DONE (`VEREDICTO: APROBADO.`).

### COLAB-DATA — Dataset sintético + LoRA + RL (Colab GPU)
- **Plan:** `lab-master/reports/samsara_forensic_20261103/PLAN_RELANZAMIENTO.md` §3
  (Fase A dataset/Data Designer → Fase B LoRA PEFT → Fase C RL GRPO/DPO
  sobre replay, todo en Colab GPU Blackwell ya conectada).
- **DoD fase A:** script `samsara_synthetic_funding.py` con
  `load_config_builder()` + muestra generada en Colab (100k filas).
- **Gates:** sin claves Meta no hay juez LLM en vivo; el host local no
  corre nada pesado (orden del usuario).
- **Estado:** QUEUED (diseño listo en el plan; ejecutar en Colab).
