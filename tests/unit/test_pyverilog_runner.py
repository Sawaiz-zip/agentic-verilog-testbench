"""
Unit tests for run().
Uses hand-crafted minimal Verilog to isolate each check category.
"""
import json
import pytest
from pipeline.analysis.pyverilog_runner import run
from pipeline.analysis.error_taxonomy import ErrorType

# ── CMB fixtures ──────────────────────────────────────────────────────────────

HALF_ADDER_DUT = """\
module half_adder(input a, input b, output sum, output cout);
    assign sum = a ^ b;
    assign cout = a & b;
endmodule
"""

# All four ports connected correctly; outputs checked via if-comparison
CORRECT_TB = """\
module tb_half_adder;
    reg a, b;
    wire sum, cout;
    half_adder dut(.a(a), .b(b), .sum(sum), .cout(cout));
    initial begin
        a = 0; b = 0; #10;
        if (sum !== 1'b0 || cout !== 1'b0)
            $display("FAIL: zero_plus_zero");
        else
            $display("PASS: zero_plus_zero");
        $finish;
    end
endmodule
"""

# cout port omitted from instantiation
MISSING_PORT_TB = """\
module tb_half_adder;
    reg a, b;
    wire sum;
    half_adder dut(.a(a), .b(b), .sum(sum));
    initial begin
        a = 0; b = 0; #10;
        if (sum !== 1'b0) $display("FAIL: test");
        else $display("PASS: test");
        $finish;
    end
endmodule
"""

# Port name "wrong_port" does not exist in the DUT
WRONG_PORT_NAME_TB = """\
module tb_half_adder;
    reg a, b;
    wire s, c;
    half_adder dut(.a(a), .b(b), .wrong_port(s), .cout(c));
    initial begin
        a = 0; b = 0; #10;
        $display("PASS: test");
        $finish;
    end
endmodule
"""

# ── SEQ fixtures ──────────────────────────────────────────────────────────────

DFF_DUT = """\
module dff(input clk, input d, output reg q);
    always @(posedge clk) q <= d;
endmodule
"""

# Correct SEQ TB: posedge clock + $display for output
SEQ_CORRECT_TB = """\
module tb_dff;
    reg clk, d;
    wire q;
    dff dut(.clk(clk), .d(d), .q(q));
    always #5 clk = ~clk;
    always @(posedge clk) begin
        $display("q=%b", q);
    end
    initial begin
        clk = 0; d = 0; #20;
        d = 1; #20;
        $finish;
    end
endmodule
"""

# TB uses @(*) always block — wrong for sequential DUT
SEQ_WRONG_SENSITIVITY_TB = """\
module tb_dff;
    reg clk, d;
    wire q;
    dff dut(.clk(clk), .d(d), .q(q));
    always @(*) begin
        $display("q=%b", q);
    end
    initial begin
        clk = 0; d = 0; #20; $finish;
    end
endmodule
"""

# TB has no $display for output q
SEQ_NO_DISPLAY_TB = """\
module tb_dff;
    reg clk, d;
    wire q;
    dff dut(.clk(clk), .d(d), .q(q));
    always @(posedge clk) begin
        d <= ~d;
    end
    initial begin
        clk = 0; d = 0; #40; $finish;
    end
endmodule
"""

# ── CMB tests ─────────────────────────────────────────────────────────────────

def test_clean_tb_no_errors():
    report = run(CORRECT_TB, HALF_ADDER_DUT, module_name="half_adder")
    assert report.parse_ok
    assert report.is_clean(), (
        f"Expected clean report but got:\n"
        f"  port_errors={report.port_errors}\n"
        f"  dataflow_errors={report.dataflow_errors}"
    )


def test_missing_port_flagged():
    report = run(MISSING_PORT_TB, HALF_ADDER_DUT, module_name="half_adder")
    assert report.parse_ok
    error_types = [e.error_type for e in report.port_errors]
    assert ErrorType.PORT_BINDING_MISMATCH in error_types, (
        f"Expected PORT_BINDING_MISMATCH in port_errors, got: {error_types}"
    )


def test_wrong_portname_flagged():
    report = run(WRONG_PORT_NAME_TB, HALF_ADDER_DUT, module_name="half_adder")
    assert report.parse_ok
    error_types = [e.error_type for e in report.port_errors]
    assert ErrorType.PORT_BINDING_MISMATCH in error_types, (
        f"Expected PORT_BINDING_MISMATCH for unknown port name, got: {error_types}"
    )


def test_parse_ok_on_valid_verilog():
    report = run(CORRECT_TB, HALF_ADDER_DUT, module_name="half_adder")
    assert report.parse_ok is True
    assert report.parser_used == "pyverilog"


def test_report_is_json_serialisable():
    report = run(CORRECT_TB, HALF_ADDER_DUT, module_name="half_adder")
    serialised = json.dumps(report.to_dict())
    parsed = json.loads(serialised)
    assert "parse_ok" in parsed
    assert "port_errors" in parsed


# ── SEQ tests ─────────────────────────────────────────────────────────────────

def test_seq_correct_tb_no_errors():
    report = run(SEQ_CORRECT_TB, DFF_DUT, module_name="dff")
    assert report.parse_ok
    assert report.is_clean(), (
        f"Expected clean SEQ report but got:\n"
        f"  sensitivity_errors={report.sensitivity_errors}\n"
        f"  fdisplay_missing={report.fdisplay_missing}"
    )


def test_seq_wrong_sensitivity_flagged():
    report = run(SEQ_WRONG_SENSITIVITY_TB, DFF_DUT, module_name="dff")
    assert report.parse_ok
    error_types = [e.error_type for e in report.sensitivity_errors]
    assert ErrorType.SENSITIVITY_LIST_ERROR in error_types, (
        f"Expected SENSITIVITY_LIST_ERROR, got: {error_types}"
    )


def test_seq_missing_fdisplay_flagged():
    report = run(SEQ_NO_DISPLAY_TB, DFF_DUT, module_name="dff")
    assert report.parse_ok
    error_types = [e.error_type for e in report.fdisplay_missing]
    assert ErrorType.MISSING_FDISPLAY in error_types, (
        f"Expected MISSING_FDISPLAY, got: {error_types}"
    )


# ── Fix A: observation criterion agrees with the standardiser ─────────────────

_SEQ_DUT = (
    "module dff(input clk, input d, output reg q);\n"
    "  always @(posedge clk) q <= d;\n"
    "endmodule\n"
)


def _seq_tb(body: str) -> str:
    return (
        "module tb;\n"
        "  reg clk, d; wire q;\n"
        "  dff uut(.clk(clk), .d(d), .q(q));\n"
        "  initial clk = 0;\n"
        "  always #5 clk = ~clk;\n"
        "  initial begin\n"
        f"{body}"
        "    $finish;\n"
        "  end\n"
        "endmodule\n"
    )


def test_self_checking_output_is_not_flagged_missing_fdisplay():
    """A testbench that checks its output with `if (q === ...)` observes that
    output. Flagging it was a false positive: the deterministic standardiser
    treats the same testbench as already observed and inserts nothing, so the
    two components contradicted each other."""
    tb = _seq_tb(
        '    d = 1; @(posedge clk); #1;\n'
        '    if (q === 1) $display("PASS: capture");\n'
        '    else $display("FAIL: capture");\n'
    )
    report = run(tb, _SEQ_DUT, module_name="dff")
    assert report.parse_ok
    types = {e.error_type.value for e in report.all_errors()}
    assert "missing_fdisplay" not in types
    assert "unobserved_output" not in types


def test_genuinely_unobserved_output_is_still_flagged():
    """The check must still fire when the output is neither printed nor compared."""
    tb = _seq_tb('    d = 1; @(posedge clk); #1;\n    $display("done");\n')
    report = run(tb, _SEQ_DUT, module_name="dff")
    assert report.parse_ok
    types = [e.error_type.value for e in report.all_errors()]
    assert "missing_fdisplay" in types


def test_unobserved_seq_output_is_reported_once_not_twice():
    """MISSING_FDISPLAY and UNOBSERVED_OUTPUT now share an observation criterion,
    so an unobserved SEQ output must not be counted twice in the taxonomy."""
    tb = _seq_tb('    d = 1; @(posedge clk); #1;\n    $display("done");\n')
    report = run(tb, _SEQ_DUT, module_name="dff")
    for_q = [e for e in report.all_errors() if e.affected_signal == "q"]
    assert len(for_q) == 1, [e.error_type.value for e in for_q]


# ── Sensitivity-list check: correct testbench styles must not be flagged ──────

def test_clock_generator_alone_is_not_a_sensitivity_error():
    """`always #5 clk = ~clk;` has no sensitivity list by design. Treating it as
    "an always-block with no edge trigger" flagged every testbench that generates
    its own clock — which is all of them."""
    tb = _seq_tb(
        '    d = 1; @(posedge clk); #1;\n'
        '    if (q === 1) $display("PASS: capture");\n'
    )
    report = run(tb, _SEQ_DUT, module_name="dff")
    types = {e.error_type.value for e in report.all_errors()}
    assert "sensitivity_list_error" not in types


def test_edge_event_control_in_initial_block_counts_as_synchronisation():
    """A self-checking testbench synchronises with `@(posedge clk)` from an
    initial block rather than with an edge-triggered always. That is edge
    synchronisation; it simply is not in a sensitivity list."""
    tb = (
        "module tb;\n"
        "  reg clk, d; wire q;\n"
        "  dff uut(.clk(clk), .d(d), .q(q));\n"
        "  initial clk = 0;\n"
        "  always #5 clk = ~clk;\n"
        "  always @(d) $display(\"d changed\");\n"   # sensitised, but not an edge
        "  initial begin\n"
        "    d = 1; @(posedge clk); #1;\n"
        "    if (q === 1) $display(\"PASS: capture\");\n"
        "    $finish;\n"
        "  end\n"
        "endmodule\n"
    )
    report = run(tb, _SEQ_DUT, module_name="dff")
    types = {e.error_type.value for e in report.all_errors()}
    assert "sensitivity_list_error" not in types


def test_no_edge_synchronisation_anywhere_is_still_flagged():
    """The check must still fire when the testbench drives a sequential DUT with
    bare delays and never synchronises to a clock edge."""
    tb = (
        "module tb;\n"
        "  reg clk, d; wire q;\n"
        "  dff uut(.clk(clk), .d(d), .q(q));\n"
        "  initial clk = 0;\n"
        "  always @(d) clk = ~clk;\n"              # sensitised, no edge, no @(posedge)
        "  initial begin\n"
        "    d = 1; #10;\n"
        "    if (q === 1) $display(\"PASS: capture\");\n"
        "    $finish;\n"
        "  end\n"
        "endmodule\n"
    )
    report = run(tb, _SEQ_DUT, module_name="dff")
    types = {e.error_type.value for e in report.all_errors()}
    assert "sensitivity_list_error" in types
