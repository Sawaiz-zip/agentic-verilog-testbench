module alu_8bit (
  input      [7:0] a,
  input      [7:0] b,
  input      [2:0] op,
  output reg [7:0] result,
  output           zero,
  output reg       carry,
  output reg       overflow
);
  wire [8:0] sum  = {1'b0, a} + {1'b0, b};
  wire [8:0] diff = {1'b0, a} - {1'b0, b};

  always @(*) begin
    carry    = 1'b0;
    overflow = 1'b0;
    case (op)
      3'b000: begin
        result   = sum[7:0];
        carry    = sum[8];
        overflow = (a[7] == b[7]) && (sum[7] != a[7]);
      end
      3'b001: begin
        result   = diff[7:0];
        carry    = (a < b);
        overflow = (a[7] != b[7]) && (diff[7] != a[7]);
      end
      3'b010: result = a & b;
      3'b011: result = a | b;
      3'b100: result = a ^ b;
      3'b101: result = a << 1;
      3'b110: result = a >> 1;
      3'b111: result = ($signed(a) < $signed(b)) ? 8'd1 : 8'd0;
      default: result = 8'd0;
    endcase
  end

  assign zero = (result == 8'b00000000);
endmodule
