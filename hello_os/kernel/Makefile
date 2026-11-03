# hello-os kernel Makefile — requiere arm-none-eabi-gcc en PATH.
# Override: make CROSS=riscv-none-elf-  (NO: el código es ARM; cambia el
# código además del CROSS si migras de ISA).
CROSS   ?= arm-none-eabi-
CC      := $(CROSS)gcc
OBJCOPY := $(CROSS)objcopy
SIZE    := $(CROSS)size

CFLAGS  := -mcpu=cortex-m4 -mthumb -O2 -ffreestanding -nostdlib
CFLAGS  += -Wall -Wextra -ffunction-sections -fdata-sections
LDFLAGS := -T linker.ld -nostdlib -Wl,--gc-sections -Wl,-Map=hello_os.map

OBJS := startup.o kernel.o

all: hello_os.elf hello_os.bin hello_os.hex size

%.o: %.s
	$(CC) $(CFLAGS) -c $< -o $@

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

hello_os.elf: $(OBJS) linker.ld
	$(CC) $(CFLAGS) $(OBJS) $(LDFLAGS) -o $@

hello_os.bin: hello_os.elf
	$(OBJCOPY) -O binary $< $@

hello_os.hex: hello_os.elf
	$(OBJCOPY) -O ihex $< $@

size: hello_os.elf
	$(SIZE) $<

clean:
	rm -f $(OBJS) hello_os.elf hello_os.bin hello_os.hex hello_os.map

.PHONY: all size clean
