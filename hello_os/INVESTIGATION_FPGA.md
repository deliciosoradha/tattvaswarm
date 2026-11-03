# INVESTIGATION — Fabric FPGA para hello-os

Objetivo: elegir FPGA + flujo para el SoC hello-os (slot Cortex-M1 +
periféricos UART/GPIO del shell `fpga/`).

## 1. Método de dimensionado (no adivinar capacidad)

1. Sintetizar `hello_soc.v` + puente CPU (TBD) en el flujo candidato.
2. Leer LUT/FF/BRAM reales del reporte y añadir **+30% de margen**.
3. Cerrar timing al reloj objetivo antes de elegir tarjeta.
4. Verificar precio/disponibilidad del distribuidor **al momento de compra**.

## 2. Familias candidatas (ejemplos a verificar, no recomendación cerrada)

| Familia (ejemplo) | Por qué se evalúa | Verificar en datasheet |
| :--- | :--- | :--- |
| Xilinx Artix-7 | Flujo Vivado maduro, tarjetas baratas | LUTs vs reporte + margen |
| Intel Cyclone V | Alternativa Quartus | Idem |
| Lattice iCE40UP / ECP5 | Flujo abierto (Yosys+nextpnr) | Idem; ojo BRAM/PLL |
| Microchip PolarFire | Seguridad/radiación si aplica | Costo vs requisito |

## 3. Núcleo CPU: licencia ARM

- El slot de integración prevé **Cortex-M1** (diseñado para FPGA) vía
  **Arm DesignStart**. Este repo NO incluye RTL de ARM.
- NO usar RTL de Cortex-M3/M4/M7 sin licencia: son núcleos distintos
  con términos diferentes. Verificar con ARM/partner.
- Alternativa abierta (si se descarta ARM): RISC-V (VexRiscv/PicoRV32) —
  implicaría reescribir `kernel/` (hoy es ARM Thumb-2).

## 4. Plan de verificación

1. Simulación: `top_tb.v` en iverilog (hecho, PASS local).
2. Síntesis + timing closure en el flujo elegido.
3. En hardware: JTAG alive → programa `.bin` → `hello os` por UART 115200 8N1.
4. Burn-in de muestra 24 h antes del lote (ver maquiladora/REQUIREMENTS.md).

## 5. Riesgos

- Pinout/constraints erróneos = tarjeta muda (mitiga: plantilla + revisión
  doble contra esquemático).
- Disponibilidad de la FPGA elegida (mitiga: segunda fuente en la BOM).
- Deriva de scope: este doc cubre selección; el paquete de manufactura vive
  en `maquiladora/REQUIREMENTS.md`.
