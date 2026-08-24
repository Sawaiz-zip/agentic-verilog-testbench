module fsm_sequence_detector (
  input            clk,
  input            rst,
  input            din,
  output           detected,
  output     [2:0] state
);
  localparam S0 = 3'd0, S1 = 3'd1, S2 = 3'd2, S3 = 3'd3, S4 = 3'd4;

  reg [2:0] cur;

  always @(posedge clk) begin
    if (rst)
      cur <= S0;
    else begin
      case (cur)
        S0: cur <= din ? S1 : S0;
        S1: cur <= din ? S1 : S2;
        S2: cur <= din ? S3 : S0;
        S3: cur <= din ? S4 : S2;
        S4: cur <= din ? S1 : S2;
        default: cur <= S0;
      endcase
    end
  end

  assign state    = cur;
  assign detected = (cur == S4);
endmodule
