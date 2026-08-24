"""
Fix C — the static-analysis evidence must survive into the result record.

`pyverilog_report` is overwritten on every repair re-analysis, so without a
per-pass trace the localisation evidence for all but the final pass is lost.
The error taxonomy (RQ1) and precision/recall (RQ2) are computed from exactly
that evidence, so it has to be persisted at write time — it cannot be
reconstructed from the saved artifacts afterwards.
"""

import json

from pipeline.nodes.pyverilog_analysis import pyverilog_analysis_node

_DUT = (
    "module dff(input clk, input d, output reg q);\n"
    "  always @(posedge clk) q <= d;\n"
    "endmodule\n"
)
_TB_UNOBSERVED = (
    "module tb;\n"
    "  reg clk, d; wire q;\n"
    "  dff uut(.clk(clk), .d(d), .q(q));\n"
    "  initial clk = 0;\n"
    "  always #5 clk = ~clk;\n"
    '  initial begin d = 1; @(posedge clk); #1; $display("done"); $finish; end\n'
    "endmodule\n"
)


def _state(**over):
    s = {"driver_rtl": _TB_UNOBSERVED, "dut_rtl": _DUT, "golden_dut": "",
         "module_name": "dff", "repair_iter": 0}
    s.update(over)
    return s


def test_analysis_node_emits_a_finding_record():
    out = pyverilog_analysis_node(_state())
    findings = out["static_findings"]
    assert len(findings) == 1
    f = findings[0]
    assert f["repair_iter"] == 0
    assert f["parse_ok"] is True
    assert f["parser_used"] == "pyverilog"
    assert "missing_fdisplay" in f["error_types"]
    assert f["errors"], "the full error objects must be kept, not just the types"


def test_finding_records_the_iteration_it_came_from():
    """Findings from different repair iterations must stay distinguishable —
    that is what makes 'did repair actually clear the flagged error?' answerable."""
    out = pyverilog_analysis_node(_state(repair_iter=2))
    assert out["static_findings"][0]["repair_iter"] == 2


def test_empty_input_still_produces_a_finding():
    """A skipped analysis is itself evidence — it must not silently vanish from
    the trace, or the per-pass record would under-count analysed runs."""
    out = pyverilog_analysis_node(_state(driver_rtl="", dut_rtl=""))
    findings = out["static_findings"]
    assert len(findings) == 1
    assert findings[0]["parse_ok"] is False
    assert findings[0]["parser_used"] == "none"


def test_static_findings_reach_the_result_json(tmp_path, monkeypatch, fake_llm, mock_icarus):
    """End-to-end: whatever the analysis node recorded must appear in the file
    the aggregator later reads."""
    monkeypatch.setenv("PIPELINE_RESULTS_DIR", str(tmp_path))
    from pipeline.nodes.evaluate import evaluate_node

    trace = [{"repair_iter": 0, "parse_ok": True, "parser_used": "pyverilog",
              "error_types": ["missing_fdisplay"], "errors": [{"error_type": "missing_fdisplay"}],
              "raw_warnings": []}]
    state = {
        "run_id": "evidence-01", "task_id": "dff", "module_name": "dff",
        "mode": "pyverilog_only", "circuit_type": "SEQ", "nl_description": "dff",
        "driver_rtl": _TB_UNOBSERVED, "dut_rtl": _DUT, "golden_dut": "",
        "mutant_duts": ["m1"], "static_findings": trace,
        "pyverilog_report": {"parse_ok": True, "parser_used": "pyverilog"},
        "repair_iter": 0, "max_repair_iter": 3, "llm_calls": [], "repair_history": [],
    }
    evaluate_node(state)

    written = json.loads((tmp_path / "evidence-01.json").read_text())
    assert written["static_findings"] == trace
    assert written["pyverilog_report"]["parser_used"] == "pyverilog"
    # Eval2 mutant validity is recorded so a low score can be told apart from
    # a score depressed by badly generated mutants.
    assert "eval2_valid_mutants" in written
    assert "eval2_total_mutants" in written
