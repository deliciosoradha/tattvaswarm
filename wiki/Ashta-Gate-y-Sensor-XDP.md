# Ashta-Gate + Sensor XDP/eBPF de aspectos

## Ashta-Gate (implementado)

`meta_hackathon_2026/ashta_gate.py`: compuerta determinista de 8
aspectos (Pṛthvī, Jala, Agni, Vāyu, Ākāśa, Manas, Buddhi, Ahaṅkāra)
sobre trazas de razonamiento. Sustituye especulación por criterio:
veto si un aspecto duro (fundamentación o falsabilidad) es cero, o si
la media ponderada cae bajo umbral. Cada veredicto se firma con el
`certificate_hash` del harness verificable y el SHA-256 de la entrada.
Shiva Router sigue siendo la esencia: la paridad decide el pool; el
Ashta-Gate decide si la respuesta vive.

Calibración pendiente (con datos, no a ojo): fijar umbrales con la
distribución de veredictos ya registrada en la telemetría de flota,
evitando el error histórico del veto al 99.87%.

## Sensor XDP/eBPF de aspectos "demoníacos" (diseño, no desplegado)

Objetivo: observar en el borde (kernel, vía XDP/eBPF) los patrones de
tráfico y de llamadas que delatan comportamiento anómalo de agentes —
exfiltración, escaneo, ráfagas hacia endpoints no autorizados —
sin tocar el flujo (modo observador primero, `XDP_PASS`).

- **Programa eBPF (XDP):** clasifica paquetes por destino/tasa y
  escribe contadores en maps BPF por "aspecto" (patrón anómalo).
- **Puente al Ashta-Gate:** un lector en espacio de usuario exporta
  los contadores como evidencia (`claims[].evidence`) para los
  aspectos Agni/Buddhi: la red aporta hechos, el gate juzga.
- **Observabilidad:** exportar a Prometheus (métricas por aspecto),
  logs a Loki con el `cert` como etiqueta, trazas Tempo por ronda.
- **Regla de despliegue:** primero `observe` (sin drop). Cualquier
  acción de bloqueo (`XDP_DROP`) es cambio de comportamiento en red:
  requiere diseño aprobado y prueba en interfaz de laboratorio, nunca
  directo en la interfaz principal.

Estado: diseño. No hay programa eBPF cargado ni reglas activas.
