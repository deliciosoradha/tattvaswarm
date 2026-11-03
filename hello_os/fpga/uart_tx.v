// uart_tx: transmisor serie 8N1 sintetizable. tx_start = pulso de 1 ciclo en IDLE.
module uart_tx #(parameter CLK_DIV = 434) (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       tx_start,
    input  wire [7:0] tx_data,
    output reg        tx_busy,
    output reg        tx
);
    localparam IDLE  = 2'd0,
               START = 2'd1,
               DATA  = 2'd2,
               STOP  = 2'd3;

    reg [1:0]  state;
    reg [15:0] clk_cnt;
    reg [2:0]  bit_idx;
    reg [7:0]  shift;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state   <= IDLE;
            clk_cnt <= 16'd0;
            bit_idx <= 3'd0;
            shift   <= 8'd0;
            tx_busy <= 1'b0;
            tx      <= 1'b1;
        end else begin
            case (state)
                IDLE: begin
                    tx <= 1'b1;
                    if (tx_start) begin
                        shift   <= tx_data;
                        bit_idx <= 3'd0;
                        clk_cnt <= 16'd0;
                        tx_busy <= 1'b1;
                        state   <= START;
                    end else begin
                        tx_busy <= 1'b0;
                    end
                end
                START: begin
                    tx <= 1'b0;
                    if (clk_cnt == CLK_DIV - 1) begin
                        clk_cnt <= 16'd0;
                        state   <= DATA;
                    end else begin
                        clk_cnt <= clk_cnt + 16'd1;
                    end
                end
                DATA: begin
                    tx <= shift[bit_idx];
                    if (clk_cnt == CLK_DIV - 1) begin
                        clk_cnt <= 16'd0;
                        if (bit_idx == 3'd7) begin
                            state <= STOP;
                        end else begin
                            bit_idx <= bit_idx + 3'd1;
                        end
                    end else begin
                        clk_cnt <= clk_cnt + 16'd1;
                    end
                end
                STOP: begin
                    tx <= 1'b1;
                    if (clk_cnt == CLK_DIV - 1) begin
                        clk_cnt <= 16'd0;
                        tx_busy <= 1'b0;
                        state   <= IDLE;
                    end else begin
                        clk_cnt <= clk_cnt + 16'd1;
                    end
                end
                default: state <= IDLE;
            endcase
        end
    end
endmodule
