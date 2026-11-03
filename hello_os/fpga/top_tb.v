// top_tb: testbench hello_soc (iverilog). Prueba TX de 'H' + GPIO. PASS/FAIL.
`timescale 1ns/1ps
module top_tb;
    reg clk = 0;
    reg rst_n = 0;
    reg bus_valid = 0, bus_we = 0, bus_re = 0;
    reg [15:0] bus_addr = 0;
    reg [7:0]  bus_wdata = 0;
    wire bus_ready;
    wire [7:0] bus_rdata;
    wire uart_tx;
    wire [7:0] gpio;
    integer pass = 0;
    integer fail = 0;

    hello_soc #(.CLK_DIV(10)) dut (
        .clk(clk), .rst_n(rst_n),
        .bus_valid(bus_valid), .bus_we(bus_we), .bus_re(bus_re),
        .bus_addr(bus_addr), .bus_wdata(bus_wdata),
        .bus_ready(bus_ready), .bus_rdata(bus_rdata),
        .uart_tx(uart_tx), .gpio(gpio)
    );

    always #10 clk = ~clk;   // 50 MHz

    task bus_write(input [15:0] a, input [7:0] d);
    begin
        @(posedge clk);
        bus_addr = a; bus_wdata = d; bus_we = 1; bus_valid = 1;
        @(posedge clk);
        bus_we = 0; bus_valid = 0;
    end
    endtask

    reg [7:0] st;
    integer t;

    initial begin
        #100 rst_n = 1;
        @(posedge clk);

        // 1) TX del byte 'H' (0x48): el start bit debe poner tx en 0.
        bus_write(16'h0000, 8'h48);
        @(posedge clk); @(posedge clk);
        if (uart_tx === 1'b0) begin pass = pass + 1; $display("PASS: start bit"); end
        else begin fail = fail + 1; $display("FAIL: start bit tx=%b", uart_tx); end

        // 2) Esperar fin de trama (busy==0) con timeout.
        st = 8'h01;
        for (t = 0; t < 5000; t = t + 1) begin
            @(posedge clk);
            bus_addr = 16'h0004; bus_re = 1; bus_valid = 1;
            @(posedge clk);
            st = bus_rdata;
            bus_re = 0; bus_valid = 0;
            if (st[0] == 1'b0) begin t = 5000; end
        end
        if (st[0] == 1'b0) begin pass = pass + 1; $display("PASS: tx idle"); end
        else begin fail = fail + 1; $display("FAIL: tx stuck busy"); end

        // 3) GPIO: escribir 0xAA y leer pines.
        bus_write(16'h0010, 8'hAA);
        @(posedge clk);
        if (gpio === 8'hAA) begin pass = pass + 1; $display("PASS: gpio"); end
        else begin fail = fail + 1; $display("FAIL: gpio=%h", gpio); end

        $display("RESULT pass=%0d fail=%0d", pass, fail);
        $finish;
    end

    initial begin
        #500000;
        $display("FAIL: timeout");
        $finish;
    end
endmodule
