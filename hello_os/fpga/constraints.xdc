## hello-os FPGA constraints — TEMPLATE
# Adapta los PACKAGE_PINs a tu tarjeta antes de sintetizar. No sintetizar
# con esta plantilla sin editar: los pines aquí son placeholders.

## Reloj del sistema (ejemplo 50 MHz)
# set_property -dict {PACKAGE_PIN <PIN_CLK> IOSTANDARD LVCMOS33} [get_ports clk]
# create_clock -period 20.000 -name sys_clk [get_ports clk]

## UART TX
# set_property -dict {PACKAGE_PIN <PIN_TX> IOSTANDARD LVCMOS33} [get_ports uart_tx]

## GPIO[7:0] (LEDs/expansión)
# set_property -dict {PACKAGE_PIN <PIN_G0> IOSTANDARD LVCMOS33} [get_ports {gpio[0]}]
# set_property -dict {PACKAGE_PIN <PIN_G1> IOSTANDARD LVCMOS33} [get_ports {gpio[1]}]
# set_property -dict {PACKAGE_PIN <PIN_G2> IOSTANDARD LVCMOS33} [get_ports {gpio[2]}]
# set_property -dict {PACKAGE_PIN <PIN_G3> IOSTANDARD LVCMOS33} [get_ports {gpio[3]}]
# set_property -dict {PACKAGE_PIN <PIN_G4> IOSTANDARD LVCMOS33} [get_ports {gpio[4]}]
# set_property -dict {PACKAGE_PIN <PIN_G5> IOSTANDARD LVCMOS33} [get_ports {gpio[5]}]
# set_property -dict {PACKAGE_PIN <PIN_G6> IOSTANDARD LVCMOS33} [get_ports {gpio[6]}]
# set_property -dict {PACKAGE_PIN <PIN_G7> IOSTANDARD LVCMOS33} [get_ports {gpio[7]}]

## Reset activo-bajo (botón)
# set_property -dict {PACKAGE_PIN <PIN_RST> IOSTANDARD LVCMOS33} [get_ports rst_n]
