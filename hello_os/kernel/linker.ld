/* hello-os linker — genérico Cortex-M. Ajusta ORIGIN/LENGTH a tu MCU/FPGA. */
ENTRY(Reset_Handler)

_estack = ORIGIN(RAM) + LENGTH(RAM);

MEMORY
{
  FLASH (rx)  : ORIGIN = 0x00000000, LENGTH = 256K
  RAM   (rwx) : ORIGIN = 0x20000000, LENGTH = 64K
}

SECTIONS
{
  .isr_vector :
  {
    KEEP(*(.isr_vector));
  } >FLASH

  .text :
  {
    *(.text*);
  } >FLASH

  .rodata :
  {
    *(.rodata*);
  } >FLASH

  .ARM.exidx :
  {
    *(.ARM.exidx*);
  } >FLASH

  _sidata = LOADADDR(.data);
  .data : ALIGN(4)
  {
    _sdata = .;
    *(.data*);
    _edata = .;
  } >RAM AT>FLASH

  .bss : ALIGN(4)
  {
    _sbss = .;
    *(.bss*);
    *(COMMON);
    _ebss = .;
  } >RAM

  /DISCARD/ :
  {
    *(.note*);
    *(.comment*);
  }
}
