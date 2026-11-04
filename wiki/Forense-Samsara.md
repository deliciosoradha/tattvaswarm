# Forense Samsara — la flota que nunca operó

Post-mortem completo en lab-master:
`reports/samsara_forensic_20261103/` (informe + paper + plan).

## Qué pasó (2026-08-01 → 2026-09-25)

La flota HFT escaneó mercados durante ~8 semanas (2.7M filas de funding,
1.5M quotes, 271k lecturas Hurst) y **no ejecutó ni una sola operación**:

| Compuerta | Evidencia |
|---|---|
| Simulación permanente | 2,374 intents, 100% `DRY_RUN` (`CC_LIVE!=1`), `positions` vacía |
| Bug web3 | 2 únicos swaps LIVE muertos: `TypeError: Unknown kwargs: ['gasPrice']` |
| Wallet en cero | `swap_guard`: 12,606/12,606 checks `blocked`, reservas siempre 0 |
| Veto estadístico | multifractal: 45,332 vetos / 60 pases (99.87%) |
| RWA sin desplegar | 3 tokens Tron `pending`, sin contrato ni txid |

## Veredicto

- **Fondos perdidos on-chain: sin evidencia.** Nada se firmó ni se envió.
- **Liquidez bloqueada: nunca desplegada.** El único payout ($32.84) lo
  rechazó el guard por wallet vacía.
- **Costo real:** oportunidad — APR 10–27% detectado y no capturado.

## Relanzamiento

Checklist go-live (fix web3 → fondeo con tope → doble llave LIVE →
recalibrar veto → canary $10) y pipeline de datos en Colab GPU:
curation → LoRA (decisión de compuerta con causa) → RL (GRPO/DPO sobre
replay histórico), en `PLAN_RELANZAMIENTO.md`. Criterio rector: liquidez
honesta y propia primero (lección deliBTC), contratos con confirmación
por transacción, cero valuaciones autodeclaradas como respaldo.
