# Reproducibilidad — cómo verificar cada cifra

## Hackathon y Puente Shiva-Muse × Tattva Swarm

```bash
python3 -m pytest tests/test_shiva_muse.py -q     # 18 passed (F1-F6 completos)
python3 auditor_estricto_meta.py .                # VEREDICTO: APROBADO. (exit code 0)
python3 meta_hackathon_2026/shiva_muse_router.py
python3 meta_hackathon_2026/shiva_muse_router.py --resume 01a1c1c5-0154-7250-8767-f4beaff19eae
```

El auditor forense (`auditor_estricto_meta.py`) devuelve **`VEREDICTO: APROBADO.`**
con código de salida `0`:
- **Saneamiento:** 0 patrones prohibidos en todo el repositorio.
- **Sección 4 (New Work Only):** Tabla explícita en [../README.md](../README.md) con mención de `meta-models/muse-spark-open-1026` y `meta-models/muse-spark-open`.
- **Inferencia de socios verificada (7 llamadas reales):** Registradas en [../meta_hackathon_2026/logs/verified_partner_inference_trace.jsonl](../meta_hackathon_2026/logs/verified_partner_inference_trace.jsonl) y sincronizadas en [../logs/verified_partner_inference_trace.jsonl](../logs/verified_partner_inference_trace.jsonl):
  - 5 llamadas a `Meta_Model_API` (`muse-spark-1.3` y `muse-wonder-1.0`, `chatcmpl-01a1a948...` a `chatcmpl-01a1a976...`).
  - 2 llamadas a `Baseten_Open_Weights` (`meta-models/muse-spark-open`, `chatcmpl-039e01de...` y `chatcmpl-9c972113...`).
- **Guardrail presupuestal:** `$0.024` usados (`<= $100.00` límite activo) y `$50.00` de reserva intacta.

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
