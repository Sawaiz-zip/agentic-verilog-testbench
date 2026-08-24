"""
Node 2 — Pyverilog static analysis with Verible fallback.
RQ1 (error taxonomy), RQ2 (pre-simulation localization).
NO LLM CALLS — deterministic analysis only.
"""

from pipeline.analysis import pyverilog_runner, verible_runner
from pipeline.state import GraphState


def pyverilog_analysis_node(state: GraphState) -> dict:
    driver_rtl = state.get("driver_rtl", "")
    # Static analysis targets the generated DUT (fallback to golden for legacy).
    dut = state.get("dut_rtl") or state.get("golden_dut", "")
    module_name = state.get("module_name", "")

    if not driver_rtl.strip() or not dut.strip():
        empty = {
            "parse_ok": False,
            "parser_used": "none",
            "port_errors": [],
            "sensitivity_errors": [],
            "dataflow_errors": [],
            "fdisplay_missing": [],
            "raw_warnings": ["driver_rtl or dut is empty — skipping analysis"],
        }
        return {
            "pyverilog_report": empty,
            "static_findings": [_finding(state, empty)],
        }

    report = pyverilog_runner.run(driver_rtl, dut, module_name=module_name)

    if not report.parse_ok:
        # Pyverilog failed — try Verible for a basic syntax check
        report = verible_runner.run(driver_rtl, dut)

    as_dict = report.to_dict()
    return {
        "pyverilog_report": as_dict,
        "static_findings": [_finding(state, as_dict)],
    }


def _finding(state: GraphState, report: dict) -> dict:
    """One record per analysis pass, kept for the whole run.

    `pyverilog_report` is overwritten on every repair re-analysis, so without
    this the localisation evidence for all but the final pass is lost — and the
    error taxonomy (RQ1) and precision/recall (RQ2) are computed from exactly
    that evidence.
    """
    errors = (
        report.get("port_errors", [])
        + report.get("sensitivity_errors", [])
        + report.get("dataflow_errors", [])
        + report.get("fdisplay_missing", [])
    )
    return {
        "repair_iter": state.get("repair_iter", 0),
        "parse_ok": report.get("parse_ok", False),
        "parser_used": report.get("parser_used", ""),
        "error_types": [e.get("error_type", "") for e in errors],
        "errors": errors,
        "raw_warnings": report.get("raw_warnings", []),
    }