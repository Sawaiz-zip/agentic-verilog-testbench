module barrel_shifter_8bit (
  input      [7:0] data_in,
  input      [2:0] shamt,
  input            dir,
  input            arith,
  output reg [7:0] data_out
);
  always @(*) begin
    if (dir == 1'b0)
      data_out = data_in << shamt;
    else if (arith == 1'b0)
      data_out = data_in >> shamt;
    else
      data_out = $signed(data_in) >>> shamt;
  end
endmodule
