"""
Batch runner for the ablation study — runs the pipeline over modules × modes.
Token-budget-aware: defaults to a small subset and refuses large sweeps without
explicit opt-in (the project is on a free API tier). RQ3/RQ4.
"""

import os
import time
import traceback
import uuid

from pipeline.config import AblationMode, PipelineConfig

# A sweep larger than this many total runs requires explicit opt-in (or a limit).
SAFE_THRESHOLD = 24

# Default small subset: the 5 verified CMB fixtures.
DEFAULT_MODULES = [
    "alu_1bit", "mux2to1", "half_adder", "comparator_2bit", "priority_encoder",
]
_SEQ_MODULES = ["dff", "counter_4bit", "shift_register"]

ALL_MODES = [
    AblationMode.BASELINE, AblationMode.RETRY_ONLY,
    AblationMode.COMPILER_ONLY,
    AblationMode.PYVERILOG_ONLY, AblationMode.HYBRID,
]


def _is_daily_rate_limit(exc: Exception) -> bool:
    """True if the exception is a rate-limit that names a *daily* token quota
    (e.g. Groq's 'tokens per day (TPD)'). These don't reset in seconds, so the
    whole sweep should abort rather than retry every remaining run."""
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    is_rate = "ratelimit" in name or "rate limit" in msg or "429" in msg
    is_daily = ("per day" in msg) or ("tpd" in msg) or ("tokens per day" in msg)
    return is_rate and is_daily


def estimate_runs(modules: list[str], modes: list, limit: int | None = None) -> int:
    """Number of (module, mode) runs a selection implies."""
    mods = modules[:limit] if limit else modules
    return len(mods) * len(modes)


def resolve_modules(selector) -> list[str]:
    """Resolve a module selector into a list of module identifiers.

    Keywords: 'cmb-fixtures'/'smoke' → the 5 CMB fixtures; 'seq-fixtures' → the SEQ
    fixtures; 'verilogeval[:N]' → the first N VerilogEval problem keys. Otherwise a
    list of explicit names (or a single name) is returned as-is.
    """
    if isinstance(selector, (list, tuple)):
        return list(selector)
    if selector in ("cmb-fixtures", "smoke"):
        return list(DEFAULT_MODULES)
    if selector == "seq-fixtures":
        return list(_SEQ_MODULES)
    if str(selector).startswith("verilogeval"):
        n = None
        if ":" in str(selector):
            try:
                n = int(str(selector).split(":", 1)[1])
            except ValueError:
                n = None
        return _verilogeval_keys(n)
    return [selector]


def _verilogeval_keys(n: int | None) -> list[str]:
    import pathlib
    root = pathlib.Path(__file__).parent.parent.parent
    d = root / "data" / "verilog_eval" / "problems"
    if not d.is_dir():
        return []
    keys = sorted(
        p.stem.replace("_prompt", "")
        for p in d.glob("*_prompt.txt")
    )
    return keys[:n] if n else keys


def _make_initial_state(module_data: dict, mode: AblationMode, run_id: str) -> dict:
    cfg = PipelineConfig(mode=mode)
    return {
        **module_data,
        "mutant_duts": [],
        "circuit_type": "CMB",
        "dut_rtl": "",
        "spec": {},
        "scenarios": [],
        "driver_rtl": "",
        "checker_py": "",
        "pyverilog_report": {},
        "error_report": [],
        "last_error_report": [],
        "scenario_results": [],
        "eval_dut_source": "generated",
        "repair_iter": 0,
        "max_repair_iter": cfg.max_repair_iter,
        "oscillation_detected": False,
        "last_repair_signature": "",
        "feedback_source": "",
        "repair_history": [],
        "eval0_pass": False,
        "eval1_pass": False,
        "eval2_pass_rate": 0.0,
        "failure_stage": None,
        "final_status": "failed_compile",
        "run_id": run_id,
        "run_started_at": time.monotonic(),
        "mode": mode.value,
        "llm_calls": [],
    }


def _default_invoke(initial_state: dict, config: PipelineConfig) -> dict:
    from pipeline.graph import build_graph
    return build_graph(config).invoke(initial_state)


def run_sweep(
    modules: list[str],
    modes: list,
    *,
    limit: int | None = None,
    opt_in: bool = False,
    results_dir: str = "results",
    graph_invoke=None,
) -> dict:
    """
    Run the pipeline over modules × modes, writing one result per run.

    Budget guard: prints the run-count estimate; if the effective run count exceeds
    SAFE_THRESHOLD and `opt_in` is False, refuses and performs ZERO runs. Per-run
    exceptions are recorded (final_status='harness_error') and the sweep continues.
    Returns {"ran", "refused", "n", "results"}.
    """
    from pipeline.__main__ import load_module  # reuse the module resolver

    mods = modules[:limit] if limit else list(modules)
    n = len(mods) * len(modes)
    print(f"[harness] planned runs: {len(mods)} modules × {len(modes)} modes = {n}")

    if n > SAFE_THRESHOLD and not opt_in:
        print(
            f"[harness] REFUSED: {n} runs exceeds the safe threshold "
            f"({SAFE_THRESHOLD}). Re-run with opt_in=True (CLI: --yes) or reduce the "
            f"selection with a limit."
        )
        return {"ran": 0, "refused": True, "n": n, "results": []}

    invoke = graph_invoke or _default_invoke

    prev_env = os.environ.get("PIPELINE_RESULTS_DIR")
    os.environ["PIPELINE_RESULTS_DIR"] = results_dir
    summaries: list[dict] = []
    ran = 0
    aborted = False
    reason = None
    try:
        for module in mods:
            if aborted:
                break
            try:
                module_data = load_module(module, None, None)
            except FileNotFoundError as e:
                print(f"[harness] skip '{module}': {e}")
                continue
            for mode in modes:
                run_id = str(uuid.uuid4())[:8]
                state = _make_initial_state(module_data, mode, run_id)
                print(f"[harness] run {module} × {mode.value} ({run_id})")
                try:
                    final = invoke(state, PipelineConfig(mode=mode))
                    ran += 1
                    summaries.append({
                        "run_id": run_id, "module": module, "mode": mode.value,
                        "final_status": final.get("final_status"),
                    })
                except Exception as exc:
                    # A daily token-quota rate limit will not clear during the
                    # sweep — abort the whole run instead of failing every remaining
                    # (module, mode) pair.
                    if _is_daily_rate_limit(exc):
                        reason = "daily_rate_limit"
                        aborted = True
                        print(
                            f"[harness] ABORTED: daily API token budget exhausted "
                            f"({exc}). Ran {ran} of {n} before stopping. Re-run once "
                            f"the quota resets, or use a smaller selection / another "
                            f"provider key."
                        )
                        break
                    # Otherwise: one bad run must not abort the sweep.
                    ran += 1
                    summaries.append({
                        "run_id": run_id, "module": module, "mode": mode.value,
                        "final_status": "harness_error", "error": str(exc),
                    })
                    print(f"[harness] ERROR {module} × {mode.value}: {exc}")
                    traceback.print_exc()
    finally:
        if prev_env is None:
            os.environ.pop("PIPELINE_RESULTS_DIR", None)
        else:
            os.environ["PIPELINE_RESULTS_DIR"] = prev_env

    return {"ran": ran, "refused": False, "aborted": aborted, "reason": reason,
            "n": n, "results": summaries}
