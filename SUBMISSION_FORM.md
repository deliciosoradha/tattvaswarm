# Formulario Cerebral Valley — campos pre-llenados (SUBMIT-02)

**Proyecto:** Shiva-Muse: Verifiable Multimodal Agent Router for Exascale GPU Physics
**Track:** Push the Frontier
**Modelos Meta usados:** Muse Spark, meta-models/muse-spark-open-1026
(Muse Spark Open), Muse Glimmer, SAM 3.1, Muse Voice Transcribe,
Muse Wonder, Muse Image, Muse Code.

## What did you build during the Hackathon? (Oct 27 – Nov 4, New Work Only)

Durante el hackathon construimos desde cero el paquete
`meta_hackathon_2026/`: (1) el orquestador combinatorio determinista
**Shiva-Muse Router**, que estratifica agentes por paridad de Hamming
sobre hipercubos bipartitos Q_n y enruta entre Muse Spark (API de Meta,
con ledger) y el modelo open-weight `meta-models/muse-spark-open-1026`
+ Muse Glimmer (Baseten, $0); (2) el inyector geométrico
**SAM 3.1 Physics Boundary Injector**, que segmenta frentes de choque e
inyecta máscaras de contorno en memoria GPU; (3) el arnés de agentes
verificables (Agents 102) con certificados SHA-256 encadenados por paso
que bloquea condiciones que violan estabilidad CFL o divergencia cero
antes de ejecutar; (4) un cortafuegos presupuestal con hard cap de
$100.00 USD activos y $50.00 USD de reserva intocable sobre los $150 de
créditos, con desborde automático a open-weights; y (5) el paper formal
de verificación compilado con Tectonic
(`paper_shiva_muse_verification.pdf`) con la tabla de deslinde
New Work Only frente a la infraestructura base preexistente
(kernels Triton SM120, 6 DOIs Zenodo previos).

## Links
- Repo: (pegar URL tras META-02 push)
- Video demo ≤3:00: (pegar tras META-05)
- Paper: `meta_hackathon_2026/paper_shiva_muse_verification.pdf`

## Estado de verificación (honesto, para notas internas — no enviar)
- Tests: pytest 5 passed (verificado en sesión).
- Inferencia en vivo contra Baseten/Meta: PENDIENTE de claves (META-01).
  Sin `request_id` reales no reclamar el premio Open Weights.
- Ledger: hard cap $100/$50 implementado y probado por test.
