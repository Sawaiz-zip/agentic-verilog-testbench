"""
Fault injectors must produce faults, not damage.

The study compares three layers — static analysis, compiler, simulator — so an
injector that emits syntactically invalid Verilog would score "the compiler
caught it" for a defect the injector itself introduced. Every injector is
therefore held to two rules: the mutation must actually change the source, and
the result must still be legal Verilog.
"""

import shutil
import subprocess

import pytest

from pipeline.analysis import fault_injection as fi

_HAS_IVERILOG = shutil.which("iverilog") is not None

_DUT = """\
module alu_8bit(input [7:0] a, input [7:0] b, input [2:0] op,
                output reg [7:0] result, output zero);
  always @(*) result = (op == 3'd0) ? a + b : a & b;
  assign zero = (result == 8'd0);
endmodule
"""

_TB = """\
module tb;
  reg [7:0] a;
  reg [7:0] b;
  reg [2:0] op;
  wire [7:0] result;
  wire zero;
  alu_8bit dut (.a(a), .b(b), .op(op), .result(result), .zero(zero));
  initial begin
    a = 8'd5; b = 8'd3; op = 3'd0;
    #10;
    if (result === 8'd8 && zero === 1'b0)
      $display("PASS: add");
    else
      $display("FAIL: add");
    $finish;
  end
endmodule
"""

_SEQ_DUT = """\
module dff(input clk, input rst, input d, output reg q);
  always @(posedge clk) begin
    if (rst) q <= 1'b0; else q <= d;
  end
endmodule
"""

_SEQ_TB = """\
module tb;
  reg clk;
  reg rst;
  reg d;
  wire q;
  dff dut (.clk(clk), .rst(rst), .d(d), .q(q));
  initial clk = 1'b0;
  always #5 clk = ~clk;
  initial begin
    rst = 1'b1; d = 1'b0;
    @(posedge clk); #1; rst = 1'b0;
    d = 1'b1;
    @(posedge clk); #1;
    if (q === 1'b1)
      $display("PASS: capture");
    else
      $display("FAIL: capture");
    $finish;
  end
endmodule
"""


def _compile(tb, dut, tmp_path):
    tb_f = tmp_path / "tb.v"
    dut_f = tmp_path / "dut.v"
    tb_f.write_text(tb)
    dut_f.write_text(dut)
    proc = subprocess.run(
        ["iverilog", "-g2012", "-o", str(tmp_path / "a.out"), str(tb_f), str(dut_f)],
        capture_output=True, text=True, timeout=60,
    )
    return proc.returncode == 0, proc.stderr


def test_baseline_testbenches_are_valid(tmp_path):
    """Guard the guard: if the unmutated fixtures do not compile, nothing below
    means anything."""
    assert _compile(_TB, _DUT, tmp_path)[0]
    assert _compile(_SEQ_TB, _SEQ_DUT, tmp_path)[0]


@pytest.mark.parametrize("dut,tb,name", [
    (_DUT, _TB, "alu_8bit"),
    (_SEQ_DUT, _SEQ_TB, "dff"),
])
def test_every_injector_changes_the_source(dut, tb, name):
    """A no-op mutation would silently report the unmutated verdict."""
    faults = fi.inject_all(tb, dut, name)
    assert faults, "no faults could be injected at all"
    for f in faults:
        assert f.testbench != tb, f"{f.kind} produced an unchanged testbench"


@pytest.mark.skipif(not _HAS_IVERILOG, reason="iverilog not installed")
@pytest.mark.parametrize("dut,tb,name", [
    (_DUT, _TB, "alu_8bit"),
    (_SEQ_DUT, _SEQ_TB, "dff"),
])
def test_mutations_are_legal_verilog(dut, tb, name, tmp_path):
    """The three-layer comparison is only meaningful if the compiler is judging
    the injected fault rather than a syntax error the injector created.

    port_rename and port_drop are exempt: an unknown or unconnected port is
    itself a compile-time condition, which is the fault being injected.
    """
    exempt = {"port_rename", "port_drop"}
    for f in fi.inject_all(tb, dut, name):
        if f.kind in exempt:
            continue
        ok, err = _compile(f.testbench, dut, tmp_path)
        assert ok, f"{f.kind} on {f.signal} produced invalid Verilog:\n{err}"


def test_expected_types_cover_the_taxonomy():
    """Each structural injector names the class it should produce, so a silent
    mismatch between injector and check cannot be mistaken for a detection."""
    faults = fi.inject_all(_TB, _DUT, "alu_8bit") + fi.inject_all(_SEQ_TB, _SEQ_DUT, "dff")
    kinds = {f.kind: f.expected_type for f in faults}
    assert kinds.get("port_rename") == "port_binding_mismatch"
    assert kinds.get("width_change") == "width_mismatch"
    assert kinds.get("undriven_input") == "undriven_input"
    assert kinds.get("remove_clock_generator") == "clock_never_toggled"


def test_swap_bindings_is_marked_undetectable():
    """The negative control must not claim a static class. Swapping two
    same-width inputs leaves both connections legal, so no structural check can
    see it — that boundary is part of the honest result."""
    faults = [f for f in fi.inject_all(_TB, _DUT, "alu_8bit")
              if f.kind == "swap_bindings"]
    assert faults, "the negative control did not apply"
    assert all(f.expected_type is None for f in faults)


def test_undriven_input_keeps_the_signal_declared_and_bound():
    """The fault is 'never assigned', not 'never declared' — otherwise it would
    be a compile error and would measure the compiler, not the analyser."""
    faults = [f for f in fi.inject_all(_TB, _DUT, "alu_8bit")
              if f.kind == "undriven_input"]
    assert faults
    for f in faults:
        assert f".{f.signal}(" in f.testbench      # still connected
        assert "_sink" in f.testbench              # assignments redirected


# ── Port-direction parsing ───────────────────────────────────────────────────
# Several injectors branch on direction: undriven_input targets inputs only,
# unobserved_output targets outputs only, swap_bindings needs two same-direction
# inputs. A parse that silently drops a port makes those injectors quietly skip
# it, which shows up as a smaller denominator rather than as an error.

@pytest.mark.parametrize("dut,expected", [
    (
        "module m(input [7:0] a, input [7:0] b, input [2:0] op,\n"
        "         output reg [7:0] result, output zero);\nendmodule\n",
        {"a": "input", "b": "input", "op": "input",
         "result": "output", "zero": "output"},
    ),
    (
        "module m(a, b, y);\n  input [7:0] a;\n  input b;\n  output y;\nendmodule\n",
        {"a": "input", "b": "input", "y": "output"},
    ),
    (
        "module f(input clk, input rst, input wr_en, input rd_en,\n"
        "  input [7:0] data_in, output reg [7:0] data_out,\n"
        "  output full, output empty);\nendmodule\n",
        {"clk": "input", "rst": "input", "wr_en": "input", "rd_en": "input",
         "data_in": "input", "data_out": "output",
         "full": "output", "empty": "output"},
    ),
])
def test_port_directions_parse_correctly(dut, expected):
    assert fi._dut_port_directions(dut) == expected


def test_port_directions_ignore_comments():
    dut = ("module m(input a, // output b is commented out\n"
           "         output y);\nendmodule\n")
    assert fi._dut_port_directions(dut) == {"a": "input", "y": "output"}
