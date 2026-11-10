# Wiki — Shiva-Muse × Tattva Swarm

Bienvenido. Esta wiki documenta el proyecto del Meta Global AI Developer
Hackathon (track **Push the Frontier**), la integración unificada
`src/tattva_swarm/` × `meta_hackathon_2026/`, y el trabajo forense asociado.

## Páginas (5 páginas)

- [Home](Home.md) — Índice general y estado de verificación del proyecto.
- [Arquitectura](Arquitectura.md) — Shiva-Muse Router, paridad
  Meru-Piṅgala sobre hipercubos Q_n, ledger $100/$50, agentes verificables,
  puente `src/tattva_swarm/muse_bridge.py` y sesión `muse resume 01a1c1c5-0154-7250-8767-f4beaff19eae`.
- [Ashta-Gate-y-Sensor-XDP](Ashta-Gate-y-Sensor-XDP.md) — Compuerta
  determinista de 8 aspectos (`ashta_gate.py`) y sensor XDP/eBPF de borde
  (`sensor_xdp/loader.py`).
- [Forense-Samsara](Forense-Samsara.md) — Post-mortem de la flota HFT:
  qué pasó, por qué nunca ejecutó, y el plan de relanzamiento.
- [Reproducibilidad](Reproducibilidad.md) — Cómo verificar cada cifra:
  suite `pytest` (18 passed), auditor estricto (`VEREDICTO: APROBADO.`),
  síntesis HK-1, simulaciones.

## Estado rápido

| Pieza | Estado |
|---|---|
| Router + pipeline E2E + paper + tests (18 passed) | ✅ verificado (`tests/test_shiva_muse.py`) |
| Auditor estricto E2E (`auditor_estricto_meta.py`) | ✅ APROBADO (7 trazas reales: 5 Meta API + 2 Baseten open-weight, $0.024 usados / $50.00 reserva) |
| Sesión Muse CLI (`01a1c1c5-0154-7250-8767-f4beaff19eae`) | ✅ integrada (`muse_session_bridge.py` + `ShivaMuseRouter.resume_session`) |
| Colab GPU (RTX PRO 6000 Blackwell) | ✅ workload swarm + Red/Blue 30 real (`RB_REAL_OK`, 15 pass / 15 veto) |
| Forense Samsara (10 DBs) | 📝 informe + paper en lab-master |
| Envíos Zenodo / Cerebral Valley / HF | 🎴 tarjetas READY en [../KANBAN.md](../KANBAN.md) |

## Regla de oro del proyecto

Ninguna cifra sin herramienta que la respalde. Lo que no se ejecutó, se
declara; lo que no se verificó, se etiqueta.
