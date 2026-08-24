import operator
from typing import Annotated, Literal, TypedDict


class GraphState(TypedDict):
    # ── Inputs ──────────────────────────────────────────────────────────────
    nl_description: str
    # task_id: logical circuit identity (the requested selector). Distinct from
    # module_name — VerilogEval tasks all share module_name "RefModule", so
    # task_id is what keeps runs distinguishable for aggregation/de-dup.
    task_id: str
    module_name: str
    # golden_dut is OPTIONAL (may be "") — used ONLY at evaluation time as a
    # benchmark reference. Generation never depends on it; it reads dut_rtl.
    golden_dut: str          # optional reference DUT, eval-only
    mutant_duts: list[str]   # for Eval2

    # ── Stage outputs ────────────────────────────────────────────────────────
    circuit_type: Literal["CMB", "SEQ"]
    dut_rtl: str                  # LLM-generated DUT (gen_dut node) — used downstream
    spec: dict                    # JSON spec: {ports, behaviour, timing}
    scenarios: list[dict]         # [{name, inputs, expected}]
    driver_rtl: str               # generated Verilog testbench
    checker_py: str               # generated Python checker
    pyverilog_report: dict        # AST + dataflow + port-binding summary
    # One entry per static-analysis pass (initial + each repair re-analysis).
    # Reducer-appended so the full localisation trace survives the repair loop
    # and lands in the result JSON — required for the error taxonomy (RQ1) and
    # precision/recall (RQ2), which cannot be reconstructed after the fact.
    static_findings: Annotated[list[dict], operator.add]
    error_report: list[dict]      # [{type, signal, line, suggested_fix, severity}]
    last_error_report: list[dict] # for oscillation detection
    scenario_results: list[dict]  # [{name, passed}] parsed from sim_output
    eval_dut_source: Literal["golden", "generated"]  # which DUT evaluate used

    # ── Loop control ─────────────────────────────────────────────────────────
    repair_iter: int
    max_repair_iter: int
    oscillation_detected: bool
    last_repair_signature: str    # error signature of previous repair (oscillation)
    feedback_source: Literal["static", "compile", "simulation", ""]
    # One entry per repair iteration; reducer-appended across the loop.
    repair_history: Annotated[list[dict], operator.add]

    # ── Evaluation ───────────────────────────────────────────────────────────
    eval0_pass: bool
    eval1_pass: bool
    eval2_pass_rate: float
    failure_stage: str | None
    final_status: Literal[
        "success",
        "failed_compile",
        "failed_eval1",
        "failed_eval2",
        "oscillated",
        "exhausted_iters",
        "invalid_dut",
    ]

    # Best-so-far testbench across repair iterations (Issue A). The repair loop
    # regenerates the whole TB, so a later iteration can be worse than an earlier
    # one; we report the highest-quality evaluated TB, not the last.
    best_snapshot: dict

    # ── Telemetry ────────────────────────────────────────────────────────────
    run_id: str
    run_started_at: float    # time.monotonic() at run entry — for end-to-end wall time
    mode: str                # ablation mode for this run (for the evaluation harness)
    # Annotated with operator.add so parallel branches (gen_driver, gen_checker)
    # each append their log entry without overwriting each other's.
    llm_calls: Annotated[list[dict], operator.add]
