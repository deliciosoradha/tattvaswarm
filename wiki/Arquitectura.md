# Arquitectura — Shiva-Muse Router × Tattva Swarm

## Idea central

Estratificar agentes por **paridad de Hamming** sobre un hipercubo
bipartito Q_n (idea Meru-Piṅgala): los vértices de peso par y los de
peso impar forman dos estratos perfectamente balanceados (2^(n-1) c/u).

- **Paridad par (color 0, dentro de presupuesto) → API comercial Meta (`Meta_Model_API`):**
  `muse-spark-1.3`, `sam-3.1`, `muse-voice-transcribe-1.0`, `muse-wonder-1.0` contra el ledger ($100 activos / $50 reserva).
- **Paridad impar (color 1), modalidad `swarm`, o desborde presupuestal → Open-Weights (`Baseten_Open_Weights`):**
  `meta-models/muse-spark-open` (`meta-models/muse-spark-open-1026`) + Muse Glimmer en Baseten (costo $0 contra créditos Meta).

## Componentes

| Archivo | Rol |
|---|---|
| `meta_hackathon_2026/shiva_muse_router.py` | `ShivaMuseRouter` + `CreditLedger` ($100/$50), `dispatch_agent_task()`, `gated_dispatch()`, `full_muse_pipeline()`, `resume_session()` |
| `meta_hackathon_2026/shiva_muse_live_engine.py` | Cliente HTTP real para `Meta_Model_API` y `Baseten_Open_Weights` con fallback `DRY_RUN_NO_KEY` y traza JSONL |
| `meta_hackathon_2026/ashta_gate.py` | Compuerta determinista de 8 aspectos ([Ashta-Gate-y-Sensor-XDP](Ashta-Gate-y-Sensor-XDP.md)) |
| `meta_hackathon_2026/wonder_dream.py` | Generación de candidatos (`dream_candidates`), manifiesto filtrado (`manifest`), danza de Shiva (`shiva_dance_resolve`) y emulación 108M Gray-code (`dream_emulate_108m`) |
| `meta_hackathon_2026/rtk_shim.py` | Compresión determinista de prompts y redacción de secretos (`redact`, `compress`) |
| `meta_hackathon_2026/sam31_physics_injector.py` | Máscaras `SAM 3.1` → tensores de contorno Dirichlet/Neumann para kernels GPU |
| `meta_hackathon_2026/verifiable_agent_harness.py` | Verificador criptográfico de invariantes PDE (`div(u)=0`, energía, CFL) con certificados SHA-256 |
| `meta_hackathon_2026/muse_session_bridge.py` | Decodificador UUIDv7 y puente de reanudación `muse resume 01a1c1c5-0154-7250-8767-f4beaff19eae` (`2026-11-09T19:24:36.052Z`) |
| `sensor_xdp/loader.py` | Lector en espacio de usuario de contadores BPF/XDP hacia evidencia para `ashta_gate` |
| `src/tattva_swarm/muse_bridge.py` | Adaptador unificado (`MuseSwarmAdapter`) que conecta `src/tattva_swarm/` (`router.py`, `cli.py`, `mcp_server.py`) con `meta_hackathon_2026/` |
| `meta_hackathon_2026/paper_shiva_muse_verification.tex` | Paper formal compilado con Tectonic (`paper_shiva_muse_verification.pdf`) |

## Guardrail financiero

- Presupuesto total de créditos: $150.00.
- Activos: **$100.00** con candado duro en el ledger (append-only JSONL).
- Reserva intocable: **$50.00**. Al acercarse al cap, el tráfico masivo
  se desborda automáticamente a open-weights ($0).
- Estado verificado en `verified_partner_inference_trace.jsonl`: 7 llamadas reales
  (5 `Meta_Model_API` + 2 `Baseten_Open_Weights`), gasto acumulado **$0.024**,
  reserva intacta **$50.00**.

## Verificable, no decorativo

Cada paso del harness deja un hash encadenado al anterior. El certificado
compromete también el `request_id` del socio cuando existe llamada real
(`chatcmpl-01a1a948...`, `chatcmpl-039e01de...`); sin claves en el entorno,
la salida se declara `DRY_RUN_NO_KEY`, nunca se simula una respuesta.

## New Work Only

Trabajo nuevo (Oct 27–Nov 4): todo `meta_hackathon_2026/` y `src/tattva_swarm/muse_bridge.py`.
Base preexistente declarada: kernels Triton SM120 y 6 DOIs de Zenodo
(10.5281/zenodo.23054158 → 23871065). La tabla de deslinde vive en
[../README.md](../README.md).
