# Kanban — Frontier Oracles + Liquidity / A2A (vivo)

**Última actualización:** 2026-11-10  
**Commit de referencia:** `20c0d25` (5 oráculos físicos + Flamholz Pareto + DharmaGate Evidence Runner)

## Columnas
- Backlog
- Ready
- In Progress
- Review / Audit
- Done
- Blocked / Rejected

## Tags
`oracle` `contract` `evidence-shield` `shiva` `meru` `dharma` `tps` `lunar` `rubisco` `reverse-translatase` `scramjet` `bounty` `a2a` `adversarial`

---

## Scientific Oracles (estado real post-commit 20c0d25)

| ID | Title | Status | Tags | Acceptance |
|----|-------|--------|------|------------|
| O-SCRAMJET | P1 Scramjet Cycle Oracle | **Done** | oracle, scramjet | Choques oblicuos NACA 1135 + Rayleigh + thermal choking; pytest PASS |
| O-TPS | P2 Multi-layer TPS Oracle | **Done** | oracle, tps | Solver 1D implícito (Thomas) + verificación analítica de placa semi-infinita (<2.5%); pytest PASS |
| O-LUNAR | P3 Lunar Power Architecture | **Done** | oracle, lunar | Balance 354 h + masa de recarga solar diurna (Li-ion / RFC / Kilopower); pytest PASS |
| O-RUBISCO | P4 Rubisco Pareto Frontier | **Done** | oracle, rubisco | Veto Flamholz et al. 2019 Dataset S2 (S=170, kcat=5 -> UNSUPPORTED_EXTRAORDINARY); pytest PASS |
| O-REVERSE | P5 Reverse Translatase | **Done** | oracle, reverse-translatase | Código genético estándar + frameshift + rango GC (35-65%); pytest PASS |
| O-RUNNER | DharmaGate Evidence Runner | **Done** | evidence-shield, dharma | `chmod 444` + `manifest.sha256` + cadena JSONL SHA-256; bundles sellados |
| O-HARNESS | Agent harness (genera → oráculo califica) | **Done** | shiva, meru, dharma | `agent_harness.py` cableado con TattvaSwarm agent + oráculos de dominio |
| O-ADVERSARIAL | Adversarial pack (vetos deterministas) | **Done** | adversarial, shiva | Casos TPS/Rubisco/Reverse/Scramjet/Lunar con 100% de veto determinista; pytest PASS |
| O-TREESERACT | Treeseract Executor (MCTS en hipercubo Q_n) | **Done** | treeseract, meru, shiva, dharma | Búsqueda MCTS proyectada en Q_n, poda física instantánea P1-P5, reformulación Shiva y sellado DharmaGate; 12/12 tests PASS |

---

## Liquidity / A2A / Bug Bounty

| ID | Title | Status | Tags | Acceptance |
|----|-------|--------|------|------------|
| B-01 | Bug bounty discovery (Immunefi / HackenProof) | **Done** | bounty | ≥3 oportunidades reales con score de riesgo y recompensa |
| B-02 | Traceable vulnerability report | **Done** | bounty, evidence-shield | Reporte + manifiesto SHA-256 sellado en evidence bundle |
| A-01 | A2A AgentCard discovery & validation | **Done** | a2a | Spoofing rechazado; cards válidas con SHA-256 |
| A-02 | A2A task delegation + evidence | **Done** | a2a, evidence-shield | Recibo de delegación sellado con Evidence Runner |
| L-SEAL | Liquidity reports sealed with same runner | **Done** | evidence-shield, bounty, a2a | `liquidity_tasks.seal_liquidity_report()` reutiliza DharmaGate Evidence Shield |
| G-01 | Sovereignty / ledger audit under load | Backlog | dharma | Cero red inesperada; ledger completo |

---

## Notas de integración

- Los 5 oráculos y el Evidence Runner están en `hackathon-submit` @ `20c0d25`.
- **Hallazgo empírico Ashta-Gate vs Oráculos de Dominio**: en pruebas adversarias sobre 50 afirmaciones absurdas bien redactadas, Ashta-Gate tuvo **100% de falso-pase** (valida estructura/léxico, no física). Los oráculos de dominio tuvieron **100% de rechazo**. La defensa real reside en los oráculos de dominio.
- `agent_harness.py` ejecuta el pipeline completo: el agente produce el candidato y el oráculo califica con tiers estrictos.
- `adversarial_cases.py` contiene los vetos que Shiva + oráculo rechazan de forma 100% determinista.
- `liquidity_tasks.py` reutiliza exactamente el mismo `seal()` / `verify()` del Evidence Shield.
- Una tarea pasa a **Done** solo cuando `verify()` es True y el veredicto es `PROXY_PASS` o integridad verificada.
