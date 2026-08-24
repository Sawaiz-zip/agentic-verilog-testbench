module traffic_light_fsm (
  input            clk,
  input            rst,
  output     [1:0] light,
  output     [1:0] timer
);
  localparam RED = 2'b00, GREEN = 2'b01, YELLOW = 2'b10;

  reg [1:0] state;
  reg [1:0] cnt;

  // Duration of the current state, in clock cycles.
  reg [1:0] dur;
  always @(*) begin
    case (state)
      RED:     dur = 2'd3;
      GREEN:   dur = 2'd3;
      YELLOW:  dur = 2'd1;
      default: dur = 2'd3;
    endcase
  end

  always @(posedge clk) begin
    if (rst) begin
      state <= RED;
      cnt   <= 2'd0;
    end else if (cnt == dur - 2'd1) begin
      cnt <= 2'd0;
      case (state)
        RED:     state <= GREEN;
        GREEN:   state <= YELLOW;
        YELLOW:  state <= RED;
        default: state <= RED;
      endcase
    end else begin
      cnt <= cnt + 2'd1;
    end
  end

  assign light = state;
  assign timer = cnt;
endmodule
