# Reproducibilidad — cómo verificar cada cifra

## Hackathon

```bash
python3 -m pytest tests/ -q            # 5 passed
python3 auditor_estricto_meta.py .     # veredicto honesto (ver abajo)
python3 meta_hackathon_2026/shiva_muse_router.py
```

El auditor hoy devuelve **RECHAZADO** por un único motivo real: no
existe `verified_partner_inference_trace.jsonl` porque no hay claves
Meta/Baseten cargadas (META-01). Todo lo demás (saneamiento, deslinde
New Work Only, artefactos) pasa. No maquillar este resultado: es el
bloqueo correcto.

## Hardware (hello-os / HK-1)

```bash
# hello_os FPGA: iverilog → RESULT 3/0 PASS
# HK-1: iverilog tb_hk1 → PASS (6,667 checks); Yosys 0.52 → 4,268 celdas
# Integridad del bundle: sha256sum -c SHA256SUMS.txt → 7/7 OK
```

Evidencia publicada en lab-master `reports/hello_hk1_20261103/`
(commit `7caca29`). La cifra de 7,810 celdas quedó retractada: provenía
de una ruta inexistente.

## Forense Samsara

- Bases (read-only): `/tmp/db_analysis/*.db`, exports `/tmp/fxcsv/*.csv`.
- Scripts: `/tmp/inspect_dbs.py`, `/tmp/analyze_funds.py`.
- Motores citados: SQLite 3.46, Apache Drill 1.22.0, Neo4j 5.26.
  Spark quedó degradado en el host (PySpark 4.1 vs JDK 25; la red cortó
  las descargas de JDK 21 y del wheel) — por orden del usuario el
  cómputo pesado va en Colab GPU, no en el host.
- Pendiente: `omnipresent.db` (~666 MB) y la búsqueda POST-03 en Drive.
  El informe es Draft hasta incorporarlas.
