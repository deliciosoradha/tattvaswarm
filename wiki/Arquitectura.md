# Arquitectura — Shiva-Muse Router

## Idea central

Estratificar agentes por **paridad de Hamming** sobre un hipercubo
bipartito Q_n (idea Meru-Piṅgala): los vértices de peso par y los de
peso impar forman dos estratos perfectamente balanceados (2^(n-1) c/u).

- **Paridad par → open-weights:** `meta-models/muse-spark-open-1026` +
  Muse Glimmer en Baseten (costo $0 contra créditos Meta).
- **Paridad impar → API comercial:** Muse Spark contra el ledger.

## Componentes

| Archivo | Rol |
|---|---|
| `meta_hackathon_2026/shiva_muse_router.py` | Router + CreditLedger con hard cap |
| `meta_hackathon_2026/sam31_physics_injector.py` | Máscaras SAM 3.1 → memoria GPU |
| `meta_hackathon_2026/verifiable_agent_harness.py` | Certificados SHA-256 encadenados |
| `meta_hackathon_2026/paper_shiva_muse_verification.tex` | Paper formal (Tectonic) |

## Guardrail financiero

- Presupuesto total de créditos: $150.
- Activos: **$100.00** con candado duro en el ledger (append-only JSONL).
- Reserva intocable: **$50.00**. Al acercarse al cap, el tráfico masivo
  se desborda a open-weights ($0).

## Verificable, no decorativo

Cada paso del harness deja un hash encadenado al anterior. Lección de la
auditoría: el certificado debe comprometer también el `request_id` del
socio cuando exista llamada real; sin claves, la salida se declara
`DRY_RUN_NO_KEY`, nunca se simula una respuesta.

## New Work Only

Trabajo nuevo (Oct 27–Nov 4): todo lo anterior. Base preexistente
declarada: kernels Triton SM120 y 6 DOIs de Zenodo
(10.5281/zenodo.23054158 → 23871065). La tabla de deslinde vive en el
README del repo.
