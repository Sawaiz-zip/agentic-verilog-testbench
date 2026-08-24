"""
Integrity of the hard-circuit evaluation fixtures.

These six circuits exist because the original fixtures cannot exercise the static
checks: four of the five cannot fire on an 8-17 line circuit with 2-4 unambiguous
ports. Each fixture must load, compile, and — critically — the analyser must stay
silent on a correct testbench for it while still catching injected structural
faults. A fixture whose golden DUT contradicts its prompt would make every
generated testbench fail Eval1 for a specification reason rather than a quality
one, so the pair is checked together.
"""

import pathlib
import shutil
import subprocess

import pytest

from pipeline.analysis.pyverilog_runner import run

_ROOT = pathlib.Path(__file__).parent.parent.parent
_CMB = _ROOT / "tests" / "fixtures" / "cmb"
_SEQ = _ROOT / "tests" / "fixtures" / "seq"

HARD_CMB = ["alu_8bit", "barrel_shifter_8bit", "bcd_to_7seg"]
HARD_SEQ = ["fsm_sequence_detector", "fifo_8x8", "traffic_light_fsm"]

_HAS_IVERILOG = shutil.which("iverilog") is not None


def _paths(name):
    d = _CMB if name in HARD_CMB else _SEQ
    return d / f"{name}_prompt.txt", d / f"{name}_ref.v"


@pytest.mark.parametrize("name", HARD_CMB + HARD_SEQ)
def test_fixture_files_exist_and_are_substantial(name):
    prompt, ref = _paths(name)
    assert prompt.exists(), f"missing prompt for {name}"
    assert ref.exists(), f"missing reference DUT for {name}"
    # The point of these fixtures is that they are not trivial.
    assert len(ref.read_text().splitlines()) >= 10
    assert f"module {name}" in ref.read_text()


@pytest.mark.parametrize("name", HARD_CMB + HARD_SEQ)
def test_prompt_names_the_module(name):
    """The description must name the module, or the generated DUT and the golden
    DUT will not share a module name and evaluation cannot bind them."""
    prompt, _ = _paths(name)
    assert name in prompt.read_text()


@pytest.mark.skipif(not _HAS_IVERILOG, reason="iverilog not installed")
@pytest.mark.parametrize("name", HARD_CMB + HARD_SEQ)
def test_reference_dut_compiles(name, tmp_path):
    _, ref = _paths(name)
    out = tmp_path / f"{name}.out"
    proc = subprocess.run(
        ["iverilog", "-g2012", "-o", str(out), str(ref)],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr


@pytest.mark.parametrize("name", HARD_CMB + HARD_SEQ)
def test_reference_dut_parses_with_pyverilog(name):
    """If Pyverilog cannot parse the golden DUT the static layer is dead for that
    circuit and only the Verible fallback remains — worth knowing before a sweep."""
    _, ref = _paths(name)
    report = run(_MINIMAL_TB[name], ref.read_text(), module_name=name)
    assert report.parse_ok, report.raw_warnings


@pytest.mark.parametrize("name", HARD_CMB + HARD_SEQ)
def test_correct_testbench_produces_no_findings(name):
    """No false positives. Every finding on these fixtures during the sweep should
    therefore correspond to a real structural defect."""
    _, ref = _paths(name)
    report = run(_MINIMAL_TB[name], ref.read_text(), module_name=name)
    assert report.all_errors() == [], [
        (e.error_type.value, e.affected_signal) for e in report.all_errors()
    ]


@pytest.mark.parametrize("name,mutate,expected", [
    ("alu_8bit", lambda tb: tb.replace(".op(op)", ".opcode(op)"), "port_binding_mismatch"),
    ("alu_8bit", lambda tb: tb.replace("op=3'd0;", ""), "undriven_input"),
    ("alu_8bit", lambda tb: tb.replace("carry===1'b0", "1'b1===1'b1"), "unobserved_output"),
    ("fifo_8x8", lambda tb: tb.replace(".rd_en(rd_en)", ".read_en(rd_en)"), "port_binding_mismatch"),
    ("fifo_8x8", lambda tb: tb.replace("data_in=8'd0;", ""), "undriven_input"),
])
def test_injected_fault_is_caught(name, mutate, expected):
    """The reason these circuits were built: the checks can finally fire."""
    _, ref = _paths(name)
    report = run(mutate(_MINIMAL_TB[name]), ref.read_text(), module_name=name)
    types = {e.error_type.value for e in report.all_errors()}
    assert expected in types, types


_MINIMAL_TB = {
    "alu_8bit": (
        "module tb;\n"
        "  reg [7:0] a,b; reg [2:0] op; wire [7:0] result; wire zero,carry,overflow;\n"
        "  alu_8bit uut(.a(a),.b(b),.op(op),.result(result),.zero(zero),"
        ".carry(carry),.overflow(overflow));\n"
        "  initial begin a=8'd1; b=8'd2; op=3'd0; #5;\n"
        "    if (result===8'd3) $display(\"PASS: r\");\n"
        "    if (zero===1'b0) $display(\"PASS: z\");\n"
        "    if (carry===1'b0) $display(\"PASS: c\");\n"
        "    if (overflow===1'b0) $display(\"PASS: o\");\n"
        "    $finish; end\n"
        "endmodule\n"
    ),
    "barrel_shifter_8bit": (
        "module tb;\n"
        "  reg [7:0] data_in; reg [2:0] shamt; reg dir,arith; wire [7:0] data_out;\n"
        "  barrel_shifter_8bit uut(.data_in(data_in),.shamt(shamt),.dir(dir),"
        ".arith(arith),.data_out(data_out));\n"
        "  initial begin data_in=8'd1; shamt=3'd1; dir=1'b0; arith=1'b0; #5;\n"
        "    if (data_out===8'd2) $display(\"PASS: shl\");\n"
        "    $finish; end\n"
        "endmodule\n"
    ),
    "bcd_to_7seg": (
        "module tb;\n"
        "  reg [3:0] bcd; wire [6:0] seg;\n"
        "  bcd_to_7seg uut(.bcd(bcd),.seg(seg));\n"
        "  initial begin bcd=4'd0; #5;\n"
        "    if (seg===7'b0111111) $display(\"PASS: zero\");\n"
        "    $finish; end\n"
        "endmodule\n"
    ),
    "fsm_sequence_detector": (
        "module tb;\n"
        "  reg clk,rst,din; wire detected; wire [2:0] state;\n"
        "  fsm_sequence_detector uut(.clk(clk),.rst(rst),.din(din),"
        ".detected(detected),.state(state));\n"
        "  initial clk=0;\n  always #5 clk=~clk;\n"
        "  initial begin rst=1'b1; din=1'b0; @(posedge clk); #1; rst=1'b0;\n"
        "    if (state===3'd0) $display(\"PASS: s\");\n"
        "    if (detected===1'b0) $display(\"PASS: d\");\n"
        "    $finish; end\n"
        "endmodule\n"
    ),
    "fifo_8x8": (
        "module tb;\n"
        "  reg clk,rst,wr_en,rd_en; reg [7:0] data_in; wire [7:0] data_out;\n"
        "  wire full,empty; wire [3:0] count;\n"
        "  fifo_8x8 uut(.clk(clk),.rst(rst),.wr_en(wr_en),.rd_en(rd_en),"
        ".data_in(data_in),.data_out(data_out),.full(full),.empty(empty),.count(count));\n"
        "  initial clk=0;\n  always #5 clk=~clk;\n"
        "  initial begin rst=1'b1; wr_en=1'b0; rd_en=1'b0; data_in=8'd0;\n"
        "    @(posedge clk); #1; rst=1'b0;\n"
        "    if (empty===1'b1) $display(\"PASS: e\");\n"
        "    if (count===4'd0) $display(\"PASS: n\");\n"
        "    if (full===1'b0) $display(\"PASS: f\");\n"
        "    if (data_out===8'd0) $display(\"PASS: d\");\n"
        "    $finish; end\n"
        "endmodule\n"
    ),
    "traffic_light_fsm": (
        "module tb;\n"
        "  reg clk,rst; wire [1:0] light; wire [1:0] timer;\n"
        "  traffic_light_fsm uut(.clk(clk),.rst(rst),.light(light),.timer(timer));\n"
        "  initial clk=0;\n  always #5 clk=~clk;\n"
        "  initial begin rst=1'b1; @(posedge clk); #1; rst=1'b0;\n"
        "    if (light===2'b00) $display(\"PASS: l\");\n"
        "    if (timer===2'd0) $display(\"PASS: t\");\n"
        "    $finish; end\n"
        "endmodule\n"
    ),
}


@pytest.mark.parametrize("name,mutate,expected", [
    # The mixed-width circuits are the reason WIDTH_MISMATCH became testable:
    # every original fixture is 1-bit or uniformly 4-bit.
    ("alu_8bit", lambda tb: tb.replace("reg [2:0] op;", "reg [1:0] op;"),
     "width_mismatch"),
    ("barrel_shifter_8bit", lambda tb: tb.replace("reg [2:0] shamt;", "reg [1:0] shamt;"),
     "width_mismatch"),
    ("bcd_to_7seg", lambda tb: tb.replace("wire [6:0] seg;", "wire [3:0] seg;"),
     "width_mismatch"),
    ("fifo_8x8", lambda tb: tb.replace("reg [7:0] data_in;", "reg [3:0] data_in;"),
     "width_mismatch"),
    # A clock that is initialised but never toggled: the simulation runs but
    # never advances, so every scenario reads back the reset value.
    ("fifo_8x8", lambda tb: tb.replace("  always #5 clk=~clk;\n", ""),
     "clock_never_toggled"),
    ("traffic_light_fsm", lambda tb: tb.replace("  always #5 clk=~clk;\n", ""),
     "clock_never_toggled"),
])
def test_width_and_clock_faults_are_caught(name, mutate, expected):
    _, ref = _paths(name)
    report = run(mutate(_MINIMAL_TB[name]), ref.read_text(), module_name=name)
    types = {e.error_type.value for e in report.all_errors()}
    assert expected in types, types
