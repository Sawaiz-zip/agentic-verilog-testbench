"""
WIDTH_MISMATCH and CLOCK_NEVER_TOGGLED.

Both target defects the compiler cannot see. A width mismatch is silent —
Verilog truncates or zero-extends without a warning, so the testbench compiles,
runs, and reports wrong results. A clock that is assigned but never toggled also
compiles and runs; the simulation simply never advances, so every scenario reads
back the reset value and the failure presents as a logic error rather than a
missing clock.

WIDTH_MISMATCH was declared in the taxonomy from the start but emitted nowhere,
and could not have been tested on the original fixtures: every one of them is
1-bit or uniformly 4-bit.
"""

import pytest

from pipeline.analysis.error_taxonomy import ErrorType
from pipeline.analysis.pyverilog_runner import run

_ALU = """\
module alu_8bit(input [7:0] a, input [7:0] b, input [2:0] op,
                output reg [7:0] result, output zero);
  always @(*) result = (op == 3'd0) ? a + b : a & b;
  assign zero = (result == 8'd0);
endmodule
"""


def _alu_tb(decls):
    return (
        "module tb;\n"
        f"{decls}"
        "  alu_8bit uut(.a(a),.b(b),.op(op),.result(result),.zero(zero));\n"
        "  initial begin a=8'd1; b=8'd2; op=3'd0; #5;\n"
        "    if (result===8'd3) $display(\"PASS: r\");\n"
        "    if (zero===1'b0) $display(\"PASS: z\");\n"
        "    $finish; end\n"
        "endmodule\n"
    )


_GOOD_DECLS = "  reg [7:0] a,b; reg [2:0] op; wire [7:0] result; wire zero;\n"


def _types(report):
    return [(e.error_type.value, e.affected_signal) for e in report.all_errors()]


def test_matching_widths_produce_no_finding():
    assert _types(run(_alu_tb(_GOOD_DECLS), _ALU, module_name="alu_8bit")) == []


@pytest.mark.parametrize("decls,signal", [
    ("  reg [7:0] a,b; reg [1:0] op; wire [7:0] result; wire zero;\n", "op"),
    ("  reg [7:0] a,b; reg [2:0] op; wire [3:0] result; wire zero;\n", "result"),
    ("  reg a; reg [7:0] b; reg [2:0] op; wire [7:0] result; wire zero;\n", "a"),
    ("  reg [7:0] a,b; reg [2:0] op; wire [7:0] result; wire [3:0] zero;\n", "zero"),
])
def test_mismatched_width_is_flagged(decls, signal):
    found = _types(run(_alu_tb(decls), _ALU, module_name="alu_8bit"))
    assert ("width_mismatch", signal) in found, found


def test_width_finding_names_both_widths_so_the_fix_is_actionable():
    decls = "  reg [7:0] a,b; reg [1:0] op; wire [7:0] result; wire zero;\n"
    report = run(_alu_tb(decls), _ALU, module_name="alu_8bit")
    item = next(e for e in report.all_errors()
                if e.error_type == ErrorType.WIDTH_MISMATCH)
    assert "3 bit" in item.suggested_fix and "2 bit" in item.suggested_fix
    assert "[2:0]" in item.suggested_fix


def test_scalar_port_bound_to_scalar_signal_is_not_flagged():
    """A port with no width declaration is 1 bit; a plain `reg` is 1 bit. These
    must compare equal rather than one of them reading as unknown."""
    report = run(_alu_tb(_GOOD_DECLS), _ALU, module_name="alu_8bit")
    assert not any(e.error_type == ErrorType.WIDTH_MISMATCH
                   for e in report.all_errors())


# ── CLOCK_NEVER_TOGGLED ──────────────────────────────────────────────────────

_DFF = """\
module dff(input clk, input d, output reg q);
  always @(posedge clk) q <= d;
endmodule
"""


def _dff_tb(clock_gen):
    return (
        "module tb;\n"
        "  reg clk, d; wire q;\n"
        "  dff uut(.clk(clk), .d(d), .q(q));\n"
        f"{clock_gen}"
        "  initial begin d=1'b1; @(posedge clk); #1;\n"
        "    if (q===1'b1) $display(\"PASS: capture\");\n"
        "    $finish; end\n"
        "endmodule\n"
    )


def test_clock_assigned_once_and_never_toggled_is_flagged():
    report = run(_dff_tb("  initial clk = 1'b0;\n"), _DFF, module_name="dff")
    assert ("clock_never_toggled", "clk") in _types(report)


@pytest.mark.parametrize("gen", [
    "  initial clk = 1'b0;\n  always #5 clk = ~clk;\n",
    "  initial clk = 1'b0;\n  initial forever #5 clk = ~clk;\n",
    "  initial clk = 1'b0;\n  always begin #5 clk = 1'b1; #5 clk = 1'b0; end\n",
    "  initial clk = 1'b0;\n  always #5 clk <= ~clk;\n",
])
def test_working_clock_generators_are_not_flagged(gen):
    """The check is deliberately generous. After three false positives in this
    module (fdisplay, sensitivity list, Eval1 verdict), an unusual but correct
    generator must never be reported."""
    report = run(_dff_tb(gen), _DFF, module_name="dff")
    assert not any(e.error_type == ErrorType.CLOCK_NEVER_TOGGLED
                   for e in report.all_errors())


def test_clock_never_assigned_at_all_is_left_to_the_undriven_check():
    """Two checks must not report the same defect: a clock with no assignment is
    an undriven input, not a clock that fails to toggle."""
    report = run(_dff_tb(""), _DFF, module_name="dff")
    types = {t for t, _ in _types(report)}
    assert "undriven_input" in types
    assert "clock_never_toggled" not in types


def test_combinational_dut_is_not_checked_for_a_clock():
    comb = ("module and2(input a, input b, output y);\n"
            "  assign y = a & b;\nendmodule\n")
    tb = ("module tb;\n  reg a,b; wire y;\n"
          "  and2 uut(.a(a),.b(b),.y(y));\n"
          "  initial begin a=1'b1;b=1'b1;#5;\n"
          "    if (y===1'b1) $display(\"PASS: and\");\n    $finish; end\n"
          "endmodule\n")
    report = run(tb, comb, module_name="and2")
    assert _types(report) == []


# ── Source-level heuristics must ignore comments and string literals ──────────
# Every text heuristic in the analyser can be answered by text that is not code.
# Each case below was observed as a real false negative — the check believed a
# signal was observed, driven, or toggled when it was not, hiding a real defect.

def test_scenario_name_containing_the_signal_does_not_count_as_observation():
    """`$display("PASS: addition_boundary_overflow")` made the `overflow` output
    look observed, so a testbench that had stopped checking it was reported clean."""
    dut = ("module m(input [7:0] a, output [7:0] result, output overflow);\n"
           "  assign result = a; assign overflow = a[7];\nendmodule\n")
    tb = ("module tb;\n"
          "  reg [7:0] a; wire [7:0] result; wire overflow;\n"
          "  m uut(.a(a), .result(result), .overflow(overflow));\n"
          "  initial begin a = 8'd1; #5;\n"
          "    if (result === 8'd1) $display(\"PASS: addition_boundary_overflow\");\n"
          "    else $display(\"FAIL: addition_boundary_overflow\");\n"
          "    $finish; end\n"
          "endmodule\n")
    report = run(tb, dut, module_name="m")
    assert ("unobserved_output", "overflow") in [
        (e.error_type.value, e.affected_signal) for e in report.all_errors()
    ]


def test_format_string_does_not_count_as_a_clock_assignment():
    """`$fdisplay(f, "clk=%b", clk)` looked like a second assignment to clk, so a
    clock that was set once and never toggled read as toggling."""
    dut = _DFF
    tb = ("module tb;\n"
          "  reg clk, rst, d; wire q; integer f;\n"
          "  dff uut(.clk(clk), .rst(rst), .d(d), .q(q));\n"
          "  initial clk = 1'b0;\n"
          "  initial begin rst = 1'b0; d = 1'b1; #10;\n"
          "    $fdisplay(f, \"clk=%b d=%b q=%b\", clk, d, q);\n"
          "    if (q === 1'b1) $display(\"PASS: capture\");\n"
          "    $finish; end\n"
          "endmodule\n")
    report = run(tb, dut, module_name="dff")
    assert "clock_never_toggled" in {e.error_type.value for e in report.all_errors()}


def test_comment_mentioning_the_signal_does_not_count_as_observation():
    dut = ("module m(input a, output y, output flag);\n"
           "  assign y = a; assign flag = ~a;\nendmodule\n")
    tb = ("module tb;\n"
          "  reg a; wire y; wire flag;\n"
          "  m uut(.a(a), .y(y), .flag(flag));\n"
          "  // TODO: check flag as well\n"
          "  initial begin a = 1'b1; #5;\n"
          "    if (y === 1'b1) $display(\"PASS: y\");\n"
          "    $finish; end\n"
          "endmodule\n")
    report = run(tb, dut, module_name="m")
    assert ("unobserved_output", "flag") in [
        (e.error_type.value, e.affected_signal) for e in report.all_errors()
    ]


def test_assignment_in_a_different_block_is_not_credited_to_an_always_block():
    """The toggle search used a fixed character window, which overran the end of a
    short always-block and picked up an assignment from a separate initial block."""
    dut = _DFF
    tb = ("module tb;\n"
          "  reg clk, rst, d; wire q;\n"
          "  dff uut(.clk(clk), .rst(rst), .d(d), .q(q));\n"
          "  always @(*) begin\n"
          "    if (q === 1'b1) $display(\"PASS: seen\");\n"
          "  end\n"
          "  initial begin clk = 1'b0; rst = 1'b0; d = 1'b0; #20; $finish; end\n"
          "endmodule\n")
    report = run(tb, dut, module_name="dff")
    assert "clock_never_toggled" in {e.error_type.value for e in report.all_errors()}
