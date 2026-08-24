"""
Node 5 — Repair loop.
Feeds structured error context back to the LLM and regenerates the testbench.
Three feedback sources trigger repair: Pyverilog static errors, compile failures
(Eval0), and simulation failures (Eval1). Bounded by max_repair_iter with
oscillation detection.
RQ3 (repair effectiveness), RQ4 (cost of repair). Model: Sonnet.
"""

from pipeline.config import AblationMode, PipelineConfig
from pipeline.llm import extract_code_block, llm_call, render_prompt
from pipeline.state import GraphState


def _error_signature(error_report: list[dict]) -> str:
    """Stable signature of an error set — used to detect oscillation (same errors
    recurring). Sorted so ordering changes do not defeat detection."""
    parts = []
    for e in error_report or []:
        etype = str(e.get("error_type", ""))
        key = str(e.get("signal") or e.get("detail") or e.get("failing_scenarios") or "")
        parts.append(f"{etype}::{key}")
    return "|".join(sorted(parts))


def _feedback_source(error_report: list[dict]) -> str:
    """Classify what kind of feedback is driving this repair."""
    types = {e.get("error_type") for e in (error_report or [])}
    if "compile_error" in types:
        return "compile"
    if "eval1_mismatch" in types:
        return "simulation"
    return "static"


def repair_node(state: GraphState) -> dict:
    """Regenerate the testbench from error feedback; detect oscillation; log the
    iteration. Never raises on malformed model output (Constitution IV)."""
    cfg = PipelineConfig()
    error_report = state.get("error_report") or []
    cur_sig = _error_signature(error_report)
    prev_sig = state.get("last_repair_signature", "")
    repair_iter = state.get("repair_iter", 0)
    source = _feedback_source(error_report)
    old_driver = state.get("driver_rtl", "")

    prompt = render_prompt(
        "repair_driver.j2",
        driver_rtl=old_driver,
        error_report=error_report,
        spec=state.get("spec") or {},
        scenarios=state.get("scenarios") or [],
        module_name=state.get("module_name", ""),
    )
    text, log = llm_call(
        node="repair",
        model=cfg.model_strong,
        prompt=prompt,
        run_id=state.get("run_id", ""),
        max_tokens=8192,
    )
    new_driver = extract_code_block(text, lang="verilog")
    if not new_driver.strip():
        new_driver = text.strip()

    # Oscillation: the same errors recurring, OR the model returning an unchanged
    # testbench. Either way, further iterations will not help — stop.
    oscillating = (
        (prev_sig and cur_sig == prev_sig)
        or new_driver.strip() == old_driver.strip()
    )

    if oscillating:
        return {
            "oscillation_detected": True,
            "last_repair_signature": cur_sig,
            "last_error_report": error_report,
            "feedback_source": source,
            "llm_calls": [log],
        }

    entry = {
        "iteration": repair_iter + 1,
        "feedback_source": source,
        "tokens_in": log.get("tokens_in", 0),
        "tokens_out": log.get("tokens_out", 0),
        "error_signature": cur_sig,
    }
    return {
        "driver_rtl": new_driver,
        "repair_iter": repair_iter + 1,
        "last_repair_signature": cur_sig,
        "last_error_report": error_report,
        "feedback_source": source,
        "repair_history": [entry],
        "llm_calls": [log],
    }


def regenerate_node(state: GraphState) -> dict:
    """RETRY_ONLY control arm — draw one more sample from gen_driver.

    Deliberately receives NO error report, no static findings and no simulator
    output: it is the same prompt gen_driver already used, sampled again. That
    makes it the control for "an extra LLM generation", which every repairing
    mode also gets. Counted as a repair iteration so the cost comparison in RQ4
    stays like-for-like.
    """
    # Imported here to avoid a circular import at module load (gen_driver imports
    # nothing from repair, but the nodes package wires both).
    from pipeline.nodes.gen_driver import gen_driver_node

    out = dict(gen_driver_node(state))
    repair_iter = state.get("repair_iter", 0)
    log = (out.get("llm_calls") or [{}])[0]
    out["repair_iter"] = repair_iter + 1
    out["feedback_source"] = "none"
    out["repair_history"] = [{
        "iteration": repair_iter + 1,
        "feedback_source": "none",
        "tokens_in": log.get("tokens_in", 0),
        "tokens_out": log.get("tokens_out", 0),
        "error_signature": "",
    }]
    return out


# ── Routing (conditional edges) ───────────────────────────────────────────────

def should_repair(state: GraphState, mode: AblationMode) -> str:
    """Post static-analysis routing: "repair", "regenerate" or "evaluate".

    Only PYVERILOG_ONLY and HYBRID repair on static-analysis errors. BASELINE
    and COMPILER_ONLY defer to the post-evaluate check. RETRY_ONLY regenerates
    exactly once, unconditionally — it never looks at the error report.
    """
    if mode is AblationMode.RETRY_ONLY:
        # Unconditional single resample: independent of whether anything was
        # flagged, which is precisely what makes it a control.
        if state.get("repair_iter", 0) == 0:
            return "regenerate"
        return "evaluate"

    if mode in (AblationMode.BASELINE, AblationMode.COMPILER_ONLY):
        return "evaluate"

    error_report = state.get("error_report") or []
    if not error_report:
        return "evaluate"
    if state.get("oscillation_detected", False):
        return "evaluate"
    if state.get("repair_iter", 0) >= state.get("max_repair_iter", 3):
        return "evaluate"

    # PYVERILOG_ONLY and HYBRID: any non-empty static error triggers repair.
    return "repair"


def should_repair_after_eval(state: GraphState, mode: AblationMode) -> str:
    """Post-evaluation routing: "repair" or "END".

    COMPILER_ONLY repairs on compile failures; HYBRID repairs on compile OR
    simulation failures. BASELINE and PYVERILOG_ONLY never repair from here.
    """
    if mode in (
        AblationMode.BASELINE,
        AblationMode.PYVERILOG_ONLY,
        AblationMode.RETRY_ONLY,
    ):
        return "END"

    # Already good → done.
    if state.get("eval0_pass", False) and state.get("eval1_pass", False):
        return "END"
    # Terminated by budget or oscillation → done.
    if state.get("oscillation_detected", False):
        return "END"
    if state.get("repair_iter", 0) >= state.get("max_repair_iter", 3):
        return "END"

    eval0 = state.get("eval0_pass", False)
    eval1 = state.get("eval1_pass", False)

    if mode == AblationMode.COMPILER_ONLY:
        return "repair" if not eval0 else "END"

    # HYBRID: repair on a compile failure or a simulation failure.
    return "repair" if (not eval0 or not eval1) else "END"


def after_repair(state: GraphState) -> str:
    """After a repair attempt: continue the loop by re-analysing, or stop.
    A repaired SEQ testbench is re-standardised (outputs re-made observable)
    before static analysis; CMB goes straight to analysis."""
    if state.get("oscillation_detected", False):
        return "evaluate"
    if state.get("repair_iter", 0) > state.get("max_repair_iter", 3):
        return "evaluate"
    if state.get("circuit_type") == "SEQ":
        return "standardise"
    return "pyverilog_analysis"
