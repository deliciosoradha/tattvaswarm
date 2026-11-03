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
