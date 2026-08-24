"""
Node 3 — LLM-based error reasoner.
Converts raw Pyverilog report into structured, actionable error list.
RQ2 (localization quality), RQ3 (LLM reasoning quality).
Model: Sonnet (strong model — reasoning about errors requires more capacity).
"""

import json

from pipeline.llm import extract_json, llm_call, render_prompt
from pipeline.state import GraphState

_SONNET = "claude-sonnet-4-6"


def error_reasoner_node(state: GraphState) -> dict:
    # Always snapshot current error_report as last (oscillation detection in repair loop)
    last_error_report = state.get("error_report") or []
    pyverilog_report = state.get("pyverilog_report") or {}

    # Skip LLM call if analysis found nothing to reason about
    all_error_lists = (
        pyverilog_report.get("port_errors", [])
        + pyverilog_report.get("clock_errors", [])
        + pyverilog_report.get("dataflow_errors", [])
        + pyverilog_report.get("fdisplay_missing", [])
    )
    if not all_error_lists:
        return {
            "last_error_report": last_error_report,
            "error_report": [],
            "llm_calls": [],
        }

    prompt = render_prompt(
        "error_reasoner.j2",
        pyverilog_report=pyverilog_report,
        spec=state.get("spec") or {},
        driver_rtl=state.get("driver_rtl") or "",
    )
    text, log = llm_call(
        node="error_reasoner",
        model=_SONNET,
        prompt=prompt,
        run_id=state.get("run_id", ""),
    )

    # Tolerant parse — robust to temperature>0 (Constitution IV). A malformed
    # response must not abort the run.
    try:
        error_report = extract_json(text)
        if not isinstance(error_report, list):
            error_report = []
    except (json.JSONDecodeError, AttributeError, ValueError):
        error_report = []

    return {
        "last_error_report": last_error_report,
        "error_report": error_report,
        "llm_calls": [log],
    }