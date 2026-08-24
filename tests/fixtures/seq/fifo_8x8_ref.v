module fifo_8x8 (
  input            clk,
  input            rst,
  input            wr_en,
  input            rd_en,
  input      [7:0] data_in,
  output reg [7:0] data_out,
  output           full,
  output           empty,
  output     [3:0] count
);
  reg [7:0] mem [0:7];
  reg [2:0] wr_ptr;
  reg [2:0] rd_ptr;
  reg [3:0] cnt;

  assign empty = (cnt == 4'd0);
  assign full  = (cnt == 4'd8);
  assign count = cnt;

  wire do_wr = wr_en && !full;
  wire do_rd = rd_en && !empty;

  always @(posedge clk) begin
    if (rst) begin
      wr_ptr   <= 3'd0;
      rd_ptr   <= 3'd0;
      cnt      <= 4'd0;
      data_out <= 8'd0;
    end else begin
      if (do_wr) begin
        mem[wr_ptr] <= data_in;
        wr_ptr      <= wr_ptr + 3'd1;
      end
      if (do_rd) begin
        data_out <= mem[rd_ptr];
        rd_ptr   <= rd_ptr + 3'd1;
      end
      case ({do_wr, do_rd})
        2'b10:   cnt <= cnt + 4'd1;
        2'b01:   cnt <= cnt - 4'd1;
        default: cnt <= cnt;
      endcase
    end
  end
endmodule
