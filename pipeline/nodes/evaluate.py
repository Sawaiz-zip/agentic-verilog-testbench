"""
Node 6 — Icarus Verilog evaluation (Eval0 / Eval1 / Eval2).
RQ3 (repair effectiveness), RQ4 (cost–quality tradeoff).
NO LLM CALLS in this node — deterministic simulation only.
"""

import json
import os
import pathlib
import time

from pipeline.config import PipelineConfig
from pipeline.eval import icarus, mutant_gen
from pipeline.reporting import parse_scenarios
from pipeline.state import GraphState

_PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent


def _resolve_status(state: GraphState, updates: dict, base_failure: str) -> str:
    """Map a failing evaluation onto the precise terminal status, accounting for
    the repair loop: oscillation and iteration-budget exhaustion take precedence
    over the raw failure kind."""
    max_iter = state.get("max_repair_iter", 3)
    if state.get("oscillation_detected", False):
        return "oscillated"
    if state.get("repair_iter", 0) >= max_iter:
        return "exhausted_iters"
    return base_failure


def _quality_score(snap: dict) -> tuple:
    """Rank an evaluated testbench for best-so-far selection (higher = better):
    passes Eval1 > catches more mutants > more scenarios pass > compiles."""
    return (
        int(bool(snap.get("eval1_pass"))),
        float(snap.get("eval2_pass_rate", 0.0)),
        int(snap.get("scenarios_passed", 0)),
        int(bool(snap.get("eval0_pass"))),
    )


def evaluate_node(state: GraphState) -> dict:
    cfg = PipelineConfig()
    t_start = time.monotonic()

    # Evaluation DUT: a supplied golden DUT (benchmark mode) if present,
    # otherwise the LLM-generated DUT. Recorded for auditability (FR-008).
    golden = (state.get("golden_dut") or "").strip()
    eval_dut = golden if golden else (state.get("dut_rtl") or "")
    eval_dut_source = "golden" if golden else "generated"

    updates: dict = {
        "eval0_pass": False,
        "eval1_pass": False,
        "eval2_pass_rate": 0.0,
        "failure_stage": None,
        "final_status": "failed_compile",
        "eval_dut_source": eval_dut_source,
        "scenario_results": [],
        "error_report": [],       # feedback for the repair loop
        "feedback_source": "",
        "llm_calls": [],
    }

    driver_rtl = state.get("driver_rtl", "")
    if not driver_rtl.strip():
        updates["failure_stage"] = "gen_driver"
        updates["final_status"] = _resolve_status(state, updates, "failed_compile")
        _write_result(state, updates, t_start)
        return updates

    if not eval_dut.strip():
        updates["failure_stage"] = "gen_dut"
        updates["final_status"] = _resolve_status(state, updates, "failed_compile")
        _write_result(state, updates, t_start)
        return updates

    # ── Eval0: compile ──────────────────────────────────────────────────────
    success, compiler_out, compiled_path = icarus.compile_tb(
        driver_rtl, eval_dut, timeout_s=cfg.simulation_timeout_s
    )
    updates["eval0_pass"] = success

    if not success:
        updates["failure_stage"] = "evaluate"
        updates["final_status"] = _resolve_status(state, updates, "failed_compile")
        # Feed the compiler error back to the repair loop (Eval0 source).
        updates["error_report"] = [{
            "error_type": "compile_error",
            "signal": "",
            "detail": compiler_out,
            "suggested_fix": "Fix the testbench so it compiles under iverilog -g2012.",
        }]
        updates["feedback_source"] = "compile"
        updates["compiler_output"] = compiler_out
        _write_result(state, updates, t_start)
        return updates

    # ── Eval1: simulate against the evaluation DUT ──────────────────────────
    sim_out = ""
    try:
        passed, sim_out = icarus.simulate_tb(
            compiled_path, timeout_s=cfg.simulation_timeout_s
        )
        updates["eval1_pass"] = passed
        updates["sim_output"] = sim_out
        updates["scenario_results"] = parse_scenarios(sim_out)
        if not passed:
            updates["failure_stage"] = "evaluate"
            updates["final_status"] = _resolve_status(state, updates, "failed_eval1")
    finally:
        if compiled_path and os.path.exists(compiled_path):
            try:
                os.unlink(compiled_path)
            except OSError:
                pass

    if not updates["eval1_pass"]:
        # Feed the failing scenarios back to the repair loop (Eval1 source).
        failing = [s["name"] for s in updates["scenario_results"] if not s.get("passed")]
        updates["error_report"] = [{
            "error_type": "eval1_mismatch",
            "signal": "",
            "failing_scenarios": failing,
            "detail": sim_out,
            "suggested_fix": (
                "The DUT is the reference. Correct the expected values for the "
                "failing scenarios to match the DUT's actual outputs."
            ),
        }]
        updates["feedback_source"] = "simulation"
        updates["driver_rtl"] = state.get("driver_rtl", "")
        updates["compiler_output"] = compiler_out
        _write_result(state, updates, t_start)
        return updates

    # ── Eval2: simulate against mutant DUTs ─────────────────────────────────
    mutant_duts = state.get("mutant_duts") or []
    if not mutant_duts:
        mutant_duts, mutant_logs = mutant_gen.generate_mutants(
            state, n=cfg.num_mutants, dut=eval_dut
        )
        updates["mutant_duts"] = mutant_duts
        updates["llm_calls"] = mutant_logs

    if mutant_duts:
        pass_rate = icarus.eval2(
            driver_rtl, mutant_duts, timeout_s=cfg.simulation_timeout_s
        )
        updates["eval2_pass_rate"] = pass_rate
        if pass_rate == 0.0:
            updates["final_status"] = "failed_eval2"
            updates["failure_stage"] = "evaluate"
        else:
            updates["final_status"] = "success"
    else:
        updates["final_status"] = "success"

    _write_result(state, updates, t_start)
    return updates


def _write_result(state: GraphState, updates: dict, t_start: float) -> None:
    # The evaluation harness can redirect output (e.g. to a tmp dir in tests) via
    # PIPELINE_RESULTS_DIR; default is the project results/ directory.
    results_dir = pathlib.Path(
        os.environ.get("PIPELINE_RESULTS_DIR") or (_PROJECT_ROOT / "results")
    )
    results_dir.mkdir(parents=True, exist_ok=True)

    run_id = state.get("run_id", "unknown")
    # Combine llm_calls already in state with any from this node (mutant gen)
    all_llm_calls = list(state.get("llm_calls") or []) + list(
        updates.get("llm_calls") or []
    )
    tokens_in_total = sum(c.get("tokens_in", 0) for c in all_llm_calls)
    tokens_out_total = sum(c.get("tokens_out", 0) for c in all_llm_calls)

    scenario_results = updates.get("scenario_results") or []
    scenarios_passed = sum(1 for s in scenario_results if s.get("passed"))

    # ── Best-so-far retention (Issue A) ──────────────────────────────────────
    # The repair loop regenerates the whole testbench, so a later iteration can be
    # WORSE than an earlier one. Track the highest-quality evaluated TB and report
    # THAT — so more repair can never yield a worse final artifact. Routing still
    # uses the *current* eval (in `updates`); only the written result uses `best`.
    current = {
        "eval0_pass": updates.get("eval0_pass", False),
        "eval1_pass": updates.get("eval1_pass", False),
        "eval2_pass_rate": updates.get("eval2_pass_rate", 0.0),
        "scenario_results": scenario_results,
        "scenarios_passed": scenarios_passed,
        "scenarios_total": len(scenario_results),
        "eval_dut_source": updates.get("eval_dut_source", "generated"),
        "driver_rtl": updates.get("driver_rtl") or state.get("driver_rtl", ""),
        "compiler_output": updates.get("compiler_output", ""),
        "sim_output": updates.get("sim_output", ""),
    }
    prev_best = state.get("best_snapshot")
    best = (
        current
        if not prev_best or _quality_score(current) > _quality_score(prev_best)
        else prev_best
    )
    # Persist for the next iteration (returned to the graph via `updates`).
    updates["best_snapshot"] = best

    # End-to-end wall time: from run entry (classify) to now, covering all repair
    # iterations. Falls back to this node's local start if the stamp is absent.
    run_started = state.get("run_started_at") or t_start
    wall_clock_ms = int((time.monotonic() - run_started) * 1000)

    result = {
        "run_id": run_id,
        "task_id": state.get("task_id") or state.get("module_name", ""),
        "module_name": state.get("module_name", ""),
        "mode": state.get("mode", ""),
        "circuit_type": state.get("circuit_type", ""),
        "nl_description": state.get("nl_description", ""),
        "repair_iter": state.get("repair_iter", 0),
        "repair_history": list(state.get("repair_history") or []),
        "feedback_source": updates.get("feedback_source", state.get("feedback_source", "")),
        "final_status": updates.get("final_status", ""),
        "failure_stage": updates.get("failure_stage"),
        # Quality fields report the best-so-far testbench (Issue A).
        "eval0_pass": best["eval0_pass"],
        "eval1_pass": best["eval1_pass"],
        "eval2_pass_rate": best["eval2_pass_rate"],
        "eval_dut_source": best["eval_dut_source"],
        "scenario_results": best["scenario_results"],
        "scenarios_passed": best["scenarios_passed"],
        "scenarios_total": best["scenarios_total"],
        "tokens_in_total": tokens_in_total,
        "tokens_out_total": tokens_out_total,
        "llm_calls": all_llm_calls,
        "wall_clock_ms": wall_clock_ms,
        # Generated DUT (the artifact produced from the description)
        "dut_rtl": state.get("dut_rtl", ""),
        # Debug fields — the best-so-far testbench and its outputs
        "driver_rtl": best["driver_rtl"],
        "compiler_output": best["compiler_output"],
        "sim_output": best["sim_output"],
    }

    out_path = results_dir / f"{run_id}.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
