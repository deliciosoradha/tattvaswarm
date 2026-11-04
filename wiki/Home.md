# Wiki — Shiva-Muse × Tattva Swarm

Bienvenido. Esta wiki documenta el proyecto del Meta Global AI Developer
Hackathon (track **Push the Frontier**) y el trabajo forense asociado.

## Páginas

- [Arquitectura](Arquitectura.md) — Shiva-Muse Router, paridad
  Meru-Piṅgala sobre hipercubos Q_n, ledger $100/$50, agentes verificables.
- [Forense-Samsara](Forense-Samsara.md) — post-mortem de la flota HFT:
  qué pasó, por qué nunca ejecutó, y el plan de relanzamiento.
- [Reproducibilidad](Reproducibilidad.md) — cómo verificar cada cifra:
  tests, auditor estricto, síntesis HK-1, simulaciones.

## Estado rápido

| Pieza | Estado |
|---|---|
| Router + paper + tests (5 passed) | ✅ verificado |
| Auditor estricto E2E | ⚠️ RECHAZADO solo por META-01 (claves) |
| Colab GPU (RTX PRO 6000 Blackwell) | ✅ workload swarm corrido |
| Forense Samsara (10 DBs) | 📝 informe + paper en lab-master |
| Envíos Zenodo / Cerebral Valley / HF | 🎴 tarjetas READY en KANBAN.md |

## Regla de oro del proyecto

Ninguna cifra sin herramienta que la respalde. Lo que no se ejecutó, se
declara; lo que no se verificó, se etiqueta.
