# REQUIREMENTS — Paquete para maquiladora (hello-os)

Documento de requisitos para cotizar y ejecutar la manufactura del hardware
hello-os (carrier FPGA + programación inicial + prueba). Idioma: español.

## 1. Objeto

Ensamble SMT, programación inicial del bitstream+firmware y prueba funcional
(UART hello) de N unidades del carrier hello-os. Diseño (esquemático/Gerbers)
lo provee ingeniería salvo acuerdo distinto.

## 2. Alcance incluido

- [ ] Procura de componentes pasivos/conectores según BOM (o consignados).
- [ ] Ensamble SMT + soldadura selectiva/TH donde aplique.
- [ ] Programación JTAG: bitstream FPGA + `hello_os.bin` en flash.
- [ ] Prueba funcional 100%: power rails, JTAG chain, UART hello 115200 8N1.
- [ ] Reporte de fallas por serial + re-trabajo acordado.

## 3. Entregables de ingeniería a la maquiladora

| # | Entregable | Estado |
| :--- | :--- | :--- |
| 1 | Esquemático + Gerbers + assembly drawings | TBD (ingeniería) |
| 2 | BOM con MP Keys / segundas fuentes | TBD — FPGA según INVESTIGATION_FPGA.md |
| 3 | Bitstream `.bit/.bin` + `hello_os.bin` + instrucciones JTAG | TBD (tras síntesis) |
| 4 | Fixture/procedimiento de prueba UART | Este repo: `fpga/top_tb.v` (sim) + criterio §4 |

## 4. Criterios de aceptación (pasa / no pasa)

1. Rails de poder dentro de ±5% sin carga y con carga.
2. Cadena JTAG detecta la FPGA a la primera.
3. Por UART 115200 8N1 se recibe `hello os` + `tick N` creciente.
4. GPIO[0] conmuta (marca de vida).
5. Muestra del lote: burn-in 24 h sin resets espurios.

## 5. BOM (resumen, detalle completo TBD con ingeniería)

| Parte | Función | Estado |
| :--- | :--- | :--- |
| FPGA | Lógica hello_soc | TBD (ver INVESTIGATION_FPGA.md §2) |
| Flash SPI | Bitstream + firmware | TBD (≥ tamaño del bitstream + 256 KB) |
| Oscilador 50 MHz | Reloj sistema | Genérico, segunda fuente |
| USB-UART bridge | Consola + programación | Genérico |
| Reguladores 3V3/1V0 | Poder | Según FPGA elegida |

## 6. Empaque y etiquetado

- Bolsa antiestática + desecante, etiqueta con serial único por unidad.
- Serial ligado al reporte de prueba (§2).

## 7. Exclusiones

- Diseño de esquemático/PCB (salvo acuerdo), certificaciones (CE/FCC/IFT),
  flete internacional e impuestos. Definir Incoterm en la cotización.

## 8. Firmas y fecha

| Rol | Nombre | Firma | Fecha |
| :--- | :--- | :--- | :--- |
| Ingeniería | TBD | | |
| Maquiladora | TBD | | |
