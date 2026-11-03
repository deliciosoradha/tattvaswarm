    .syntax unified
    .cpu cortex-m4
    .thumb

    /* Tabla de vectores: 16 excepciones + 32 IRQs (todas por defecto).
       Válida para Cortex-M0+/M3/M4/M7 (solo usa instrucciones básicas). */
    .section .isr_vector,"a",%progbits
    .type __isr_vector, %object
    .global __isr_vector
__isr_vector:
    .word _estack
    .word Reset_Handler
    .word NMI_Handler
    .word HardFault_Handler
    .word MemManage_Handler
    .word BusFault_Handler
    .word UsageFault_Handler
    .word 0
    .word 0
    .word 0
    .word 0
    .word SVC_Handler
    .word DebugMon_Handler
    .word 0
    .word PendSV_Handler
    .word SysTick_Handler
    .rept 32
    .word Default_Handler
    .endr

    .section .text.Reset_Handler,"ax",%progbits
    .type Reset_Handler, %function
    .global Reset_Handler
Reset_Handler:
    /* Copia .data: FLASH (LMA) -> RAM (VMA). */
    ldr r0, =_sidata
    ldr r1, =_sdata
    ldr r2, =_edata
    subs r2, r2, r1
    ble .L_data_done
.L_data_loop:
    subs r2, r2, #4
    ldr r3, [r0, r2]
    str r3, [r1, r2]
    bne .L_data_loop
.L_data_done:
    /* Limpia .bss. */
    ldr r1, =_sbss
    ldr r2, =_ebss
    subs r2, r2, r1
    ble .L_bss_done
    movs r0, #0
.L_bss_loop:
    subs r2, r2, #4
    str r0, [r1, r2]
    bne .L_bss_loop
.L_bss_done:
    bl main
    b .                       /* main retornó: detener */

    .section .text.Default_Handler,"ax",%progbits
    .type Default_Handler, %function
    .global Default_Handler
Default_Handler:
    b .

    /* Aliases débiles: el kernel puede sobreescribir cualquier handler. */
    .weak NMI_Handler, HardFault_Handler, MemManage_Handler
    .weak BusFault_Handler, UsageFault_Handler, SVC_Handler
    .weak DebugMon_Handler, PendSV_Handler, SysTick_Handler
    .thumb_set NMI_Handler, Default_Handler
    .thumb_set HardFault_Handler, Default_Handler
    .thumb_set MemManage_Handler, Default_Handler
    .thumb_set BusFault_Handler, Default_Handler
    .thumb_set UsageFault_Handler, Default_Handler
    .thumb_set SVC_Handler, Default_Handler
    .thumb_set DebugMon_Handler, Default_Handler
    .thumb_set PendSV_Handler, Default_Handler
    .thumb_set SysTick_Handler, Default_Handler
