# hello-os — ARM Cortex-M + FPGA

Minimal OS ("hello") sobre ARM Cortex-M con shell FPGA propio, investigación
de hardware y paquete de requirements para maquiladora.

## Layout

```text
hello_os/
  README.md                  # este archivo
  kernel/
    startup.s                # tabla de vectores + Reset_Handler (Cortex-M genérico)
    kernel.c                 # kernel freestanding: UART hello + tick
    linker.ld                # FLASH 256K @0x0, RAM 64K @0x20000000
    Makefile                 # arm-none-eabi-gcc (CROSS configurable)
  fpga/
    hello_soc.v              # top: bus de periféricos + slot de integración CPU
    uart_tx.v                # UART TX 8N1 sintetizable
    top_tb.v                 # testbench (iverilog): TX + GPIO, PASS/FAIL
    constraints.xdc          # TEMPLATE: adaptar PACKAGE_PINs a tu tarjeta
  INVESTIGATION_FPGA.md      # dimensionado, familias candidatas, riesgos
  maquiladora/
    REQUIREMENTS.md          # paquete para la maquiladora (BOM, aceptación)
```

## Mapa de memoria del SoC (definido por hello-os)

| Base       | Periférico | Registros                          |
| ---------- | ---------- | ---------------------------------- |
| 0x40000000 | UART0      | +0x00 TXDATA (w), +0x04 STATUS (r, bit0=busy) |
| 0x40001000 | GPIO       | +0x00 OUT (w, 8 bits)              |

## Build

```bash
# Kernel (requiere arm-none-eabi-gcc)
cd hello_os/kernel && make        # -> hello_os.elf/.bin/.hex

# Simulación FPGA (requiere iverilog, verificado local)
cd hello_os/fpga && iverilog -o /tmp/top_tb hello_soc.v uart_tx.v top_tb.v && vvp /tmp/top_tb
```

## Notas honestas

- `startup.s`/`linker.ld` son genéricos Cortex-M (M0+/M3/M4/M7). Ajusta
  `MEMORY` a tu MCU/FPGA real.
- El núcleo CPU en FPGA es **slot de integración**: usa un Cortex-M1 bajo
  licencia (Arm DesignStart); este repo NO incluye RTL de ARM.
- `constraints.xdc` es plantilla: define los pines de tu tarjeta.
- Sin `arm-none-eabi-gcc` instalado no hay cross-compile local; el CI/target
  lo compila (ver POST-02/G4 para runs con hardware).
