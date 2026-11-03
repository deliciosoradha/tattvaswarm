// hello_soc: shell FPGA de hello-os. Bus de periféricos + UART + GPIO.
// SLOT DE INTEGRACIÓN: el maestro del bus será un núcleo ARM Cortex-M1 bajo
// licencia (Arm DesignStart). Este repo NO incluye RTL de ARM: el puente
// AHB-Lite -> bus-periférico es TBD de integración (ver INVESTIGATION_FPGA.md).
// En simulación el testbench maneja el bus directamente.
module hello_soc #(parameter CLK_DIV = 434) (
    input  wire        clk,
    input  wire        rst_n,
    // Bus de periféricos (lado maestro: CPU una vez integrada)
    input  wire        bus_valid,
    input  wire        bus_we,
    input  wire        bus_re,
    input  wire [15:0] bus_addr,
    input  wire [7:0]  bus_wdata,
    output wire        bus_ready,
    output wire [7:0]  bus_rdata,
    // Pines
    output wire        uart_tx,
    output wire [7:0]  gpio
);
    // Mapa: 0x00 UART_TXDATA (w), 0x04 UART_STATUS (r, bit0=busy),
    //       0x10 GPIO_OUT (w).
    wire tx_start = bus_valid & bus_we & (bus_addr == 16'h0000);
    wire tx_busy;
    reg  [7:0] gpio_r;

    assign bus_ready = 1'b1;   // periféricos de 1 ciclo
    assign bus_rdata = (bus_re && (bus_addr == 16'h0004))
                       ? {7'b0, tx_busy} : 8'h00;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            gpio_r <= 8'h00;
        end else if (bus_valid && bus_we && (bus_addr == 16'h0010)) begin
            gpio_r <= bus_wdata;
        end
    end
    assign gpio = gpio_r;

    uart_tx #(.CLK_DIV(CLK_DIV)) u_uart (
        .clk      (clk),
        .rst_n    (rst_n),
        .tx_start (tx_start),
        .tx_data  (bus_wdata),
        .tx_busy  (tx_busy),
        .tx       (uart_tx)
    );
endmodule
