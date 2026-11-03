/* hello-os kernel — ARM Cortex-M, freestanding. Sin libc, sin semihosting.
 * Mapa SoC propio: UART0 @0x40000000 (TXDATA+0x00 w, STATUS+0x04 r bit0=busy),
 * GPIO @0x40001000 (OUT+0x00 w). Ver hello_os/README.md y fpga/hello_soc.v
 * (el STATUS bit0 lo maneja el periférico uart_tx del shell FPGA).
 */
#include <stdint.h>

#define UART0_BASE 0x40000000u
#define UART_DR    (*(volatile uint32_t *)(UART0_BASE + 0x00u))
#define UART_FR    (*(volatile uint32_t *)(UART0_BASE + 0x04u))
#define UART_FR_BUSY (1u << 0)

#define GPIO_BASE  0x40001000u
#define GPIO_OUT   (*(volatile uint32_t *)(GPIO_BASE + 0x00u))

static void uart_putc(char c)
{
    while ((UART_FR & UART_FR_BUSY) != 0u) { /* espera TX libre */ }
    UART_DR = (uint32_t)c;
}

static void uart_puts(const char *s)
{
    while (*s != '\0') {
        uart_putc(*s++);
    }
}

/* Decimal sin división (evita dependencia de libgcc con -nostdlib). */
static void uart_putu32(uint32_t v)
{
    static const uint32_t pow10[] = {
        1000000000u, 100000000u, 10000000u, 1000000u, 100000u,
        10000u, 1000u, 100u, 10u, 1u
    };
    int i;
    int started = 0;
    for (i = 0; i < 10; i++) {
        uint32_t d = 0u;
        while (v >= pow10[i]) {
            v -= pow10[i];
            d++;
        }
        if (d != 0u || started || i == 9) {
            uart_putc((char)('0' + d));
            started = 1;
        }
    }
}

static void delay(volatile uint32_t n)
{
    while (n-- != 0u) {
        __asm__ volatile ("nop");
    }
}

int main(void)
{
    uint32_t tick = 0u;

    GPIO_OUT = 0x01u;              /* marca de vida en GPIO[0] */
    uart_puts("hello os\r\n");

    for (;;) {
        uart_puts("tick ");
        uart_putu32(tick++);
        uart_puts("\r\n");
        GPIO_OUT ^= 0x01u;
        delay(1000000u);
    }
    /* no retorna */
}
