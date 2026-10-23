# Plan de verificación — TattvaSwarm (Dharmagate Agentic Shield)

> Generado 2026-10-23 tras la revisión del código público y la puesta en marcha
> del demo vivo. Objetivo: cerrar todo lo que quedó pendiente o no verificado,
> con criterios de aceptación medibles. Cada item tiene un comando de verificación.

## 0. Aclaración: el proyecto "dharmagate-agentic-shield" en GitLab

El proyecto original `radhikatmosphere/servicios/dharmagate-agentic-shield` (id 87452385)
**ya estaba en estado `deletion_scheduled` antes de esta sesión** — no lo borré yo.
Lo que borré fue el duplicado vacío que creé por error:
`radhikatmosphere/servicios/dharmagate-tattvaswarm` (id 87989426), porque el grupo
`radhikatmosphere/servicios` es privado y por tanto sus GitLab Pages serían privadas,
inútiles para un demo público. Lo recreé como `axelpadilla98/dharmagate-tattvaswarm`
(id 87989433, público, Pages público). Verificación:

```bash
glab api "projects?search=dharmagate&simple=true&per_page=20" | python3 -c "import sys,json;[print(p['path_with_namespace'],p['visibility'],p.get('pages_access_level')) for p in json.load(sys.stdin)]"
# esperado: axelpadilla98/dharmagate-tattvaswarm public public
```

## A. Código — hallazgos de la revisión

### A1. Bug de emparejamiento en el conductor (CRÍTICO) — ✅ FIXED
- **Dónde:** `src/tattva_swarm/conductor.py:107` (`zip(tasks, results)`).
- **Problema:** empareja por índice entre tareas (orden original) y resultados
  (ordenados por id). Falsos `REJECTED` cuando los ids no siguen el orden del spec.
- **Verificación (reproduce):** spec con ids `["zeta","alfa"]` → ambas tareas
  correctas dieron `REJECTED: mismatch` (ya reproducido).
- **Fix:** construir `by_id = {r["id"]: r for r in results}` y verificar
  `by_id[t.get("id")]`.
- **Aceptación:** añadir test `test_conductor_pairing_by_id` con ids desordenados;
  `pytest -q` verde y veredictos `VERIFIED`.

### A2. Tier `small` es un stub
- **Dónde:** `router.py:117-125`.
- **Decisión requerida:** (a) implementar lógica local real (memoria/reglas) o
  (b) documentar explícitamente que `small` es un no-op clasificador.
- **Aceptación:** o bien código con tests, o README/SUBMISSION dicen "small = clasificado
  como local, sin LLM (sin lógica de negocio)".

### A3. "Allowlist explícita" solo documentación
- **Dónde:** `docs/SOVEREIGNTY.md` vs código.
- **Decisión:** implementar enforcement (lista de hosts permitidos + bloqueo) o
  bajar el claim a "ledger de uso + política documentada".
- **Aceptación:** si se implementa, test que bloquea host no allowlisted; si no,
  README dice "política documentada, no enforcement en código".

### A4. Sandbox "hardened" sobrestimado
- **Dónde:** `sandbox.py` `_run_docker`/`_run_rust`.
- **Fix opcional:** añadir `--read-only`, `--cap-drop=ALL`, `--security-opt=no-new-privileges`,
  `--user 65534`. Documentar límites.
- **Aceptación:** `docker inspect` del contenedor muestra los flags; test de escape.

### A5. `qdrant_context.py` código muerto
- **Dónde:** `src/tattva_swarm/qdrant_context.py`.
- **Decisión:** cablearlo al swarm (context provider real) o mover a `examples/`
  y quitarlo de las features anunciadas.
- **Aceptación:** o bien usado por `conductor`/MCP, o bien README no lo lista como feature.

### A6. Inconsistencia documental research tier — ✅ FIXED
- **Dónde:** `docs/HACKATHON.md` ("Not run / not claimed") vs `docs/EVIDENCE.md §7`
  y `docs/SUBMISSION.md` ("5 results, 0.33 s").
- **Fix:** reconciliar: EVIDENCE tiene la evidencia; HACKATHON debe decir
  "verificado en EVIDENCE §7, requiere TAVILY_API_KEY".
- **Aceptación:** grep no muestra contradicción.

### A7. `run_graph` no cumple "never raises" — ✅ FIXED
- **Dónde:** `conductor.py:55` `_run_task` (`task["prompt"]`).
- **Fix:** usar `task.get("prompt", "")` y devolver error estructurado.
- **Aceptación:** test con spec sin `prompt` → `status=error`, sin excepción.

### A8. Verificador acepta "VERIFIED…" — ✅ FIXED
- **Dónde:** `conductor.py:72` (`verdict_text.upper().startswith("VERIFIED")`).
- **Fix:** parsear token exacto (`verdict_text.strip().upper() == "VERIFIED"` o regex).
- **Aceptación:** "VERIFIED but wrong" → `REJECTED`.

### A9. Claim 108 M / A100 no reproducible
- **Dónde:** `docs/EVIDENCE.md §1`, README.
- **Decisión:** mantener (etiquetado como externo, no reproducible) o bajar a los
  números del repo (100 k / 4.25 s Python; 0.030 s Rust).
- **Aceptación:** si se mantiene, README dice "motor escalado externo, no incluido".

### A10. LoRA jobs pendientes
- **Dónde:** `docs/POST_TRAINING.md`.
- **Acción:** re-poll con `training/tf_post_train.py --poll`; actualizar estados.
- **Aceptación:** docs reflejan el estado real (running/done/failed) con fecha.

## B. Unificación de nombres

### B1. Devpost (MANUAL — sin credenciales de agente)
- Cambiar título a un solo nombre: "Dharmagate Agentic Shield (TattvaSwarm)" o
  decidir uno. Slug actual: `dharmagate-agentic-shield`.
- Reemplazar video (ver C).
- **Verificación:** `curl devpost.com/software/dharmagate-agentic-shield` muestra el
  nuevo título y el video correcto (no `Jm4v_h4DW7o`).

### B2. Repo GitHub (HECHO)
- Descripción: "Dharmagate Agentic Shield (TattvaSwarm) — sovereign personal AI swarm …"
- README: sección "Live demo (GitHub Pages)".
- **Verificación:** `gh repo view deliciosoradha/tattvaswarm --json description`.

### B3. Demo (HECHO)
- https://deliciosoradha.github.io/tattvaswarm/ con badge "= TattvaSwarm".
- **Verificación:** `curl -s … | grep -o '<title>.*</title>'`.

## C. Demo vivo — verificación end-to-end

### C1. Pages
```bash
curl -s -o /dev/null -w '%{http_code}\n' https://deliciosoradha.github.io/tattvaswarm/
# esperado: 200
```

### C2. Proxy health + CORS
```bash
curl -s https://tattva-nim-proxy.axelpadilla98.workers.dev/healthz
curl -s -D - -o /dev/null -X OPTIONS https://tattva-nim-proxy.axelpadilla98.workers.dev/api/route \
  -H "Origin: https://deliciosoradha.github.io" -H "Access-Control-Request-Method: POST" \
  | grep -i access-control-allow-origin
# esperado: https://deliciosoradha.github.io
```

### C3. Paridad del clasificador (JS vs Python)
- Comparar `classify()` del demo con `router.classify` para un corpus de 20 prompts
  (incluyendo español/inglés, >1200 chars, >4000 chars, research hints).
- **Aceptación:** 20/20 coincidencias de tier.

### C4. Llamada viva (normal / reasoning / heavy)
```bash
for t in normal reasoning heavy; do
  curl -s -X POST https://tattva-nim-proxy.axelpadilla98.workers.dev/api/route \
    -H "Content-Type: application/json" \
    -d "{\"prompt\":\"What is local-first software? One sentence.\",\"tier\":\"$t\",\"max_tokens\":512}" \
    | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['tier'], d['status'], (d.get('reply') or '')[:40])"
done
# esperado: 3 líneas status=ok con contenido no vacío
```

### C5. Video en Devpost (ASSET CREADO — upload manual)
- Asset listo en `devpost-assets/tattvaswarm-demo.mp4` (136 s, captions quemados) +
  `.srt`/`.vtt` + thumbnail 1200x800. Falta subir el MP4 a YouTube y pegar la URL
  en el campo Video de Devpost (manual, sin credenciales de agente).
- **Verificación:** el embed de la página ya no es `Jm4v_h4DW7o`.

## D. Git — estado de ramas

- GitHub `main`: HEAD `50885f5` (pushed).
- Commit local no publicado `d60243e` (Taylor-Green benchmark, de `shiva-swarm`) — decidir si se pusha o se queda local.
- **Verificación:** `git log origin/main..HEAD` en el clone local.

## E. Orden de ejecución sugerido

1. A1 + A7 + A8 (fixes de código, con tests) — 1 sesión.
2. A6 (reconciliar docs) — 10 min.
3. C3 + C4 (verificación demo) — 10 min.
4. A2, A3, A4, A5, A9, A10 (decisiones de scope) — discutir con operador.
5. B1 + C5 (Devpost manual) — operador.

## F. Criterio de "terminado"

- `pytest -q` verde con tests nuevos A1/A7/A8.
- Demo vivo devuelve 200 y 3 tiers con contenido.
- Devpost sin video ajeno.
- Un solo nombre en README, repo, demo y Devpost.
