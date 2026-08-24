"""
CLI entry point.
Usage:
  python -m pipeline run --module Prob005_notgate
  python -m pipeline run --module half_adder --mode baseline
  python -m pipeline run --module my_mod --nl desc.txt --dut dut.v
"""

import argparse
import pathlib
import sys
import uuid

from dotenv import load_dotenv
load_dotenv()  # must be before any module that reads ANTHROPIC_API_KEY

_PROJECT_ROOT = pathlib.Path(__file__).parent.parent
_VERILOG_EVAL_DIR = _PROJECT_ROOT / "data" / "verilog_eval" / "problems"
_FIXTURES_CMB = _PROJECT_ROOT / "tests" / "fixtures" / "cmb"
_FIXTURES_SEQ = _PROJECT_ROOT / "tests" / "fixtures" / "seq"


def load_module(
    module_name: str,
    nl_override: str | None,
    dut_override: str | None,
) -> dict:
    """
    Return {"task_id", "module_name", "nl_description", "golden_dut"}.

    `task_id` is the logical circuit identity (the requested selector). It is
    distinct from `module_name`, which is the *Verilog* module name the DUT/TB
    must use (VerilogEval golden refs are all named "RefModule", so every
    VerilogEval task shares that module_name — task_id keeps them distinguishable
    for de-duplication and aggregation).

    golden_dut may be "" — the pipeline generates its own DUT from the
    description. A golden DUT, when present, is used at evaluation time only.

    Search order (explicit fixtures take precedence over fuzzy dataset matches):
      1. --nl override (description-only user flow); --dut optional (eval-only)
      2. data/verilog_eval/problems/<module_name>_prompt.txt + _ref.sv (exact)
      3. tests/fixtures/cmb/<module_name>_prompt.txt + _ref.v
      4. tests/fixtures/seq/<module_name>_prompt.txt + _ref.v
      5. partial VerilogEval match (e.g. "notgate" → Prob005_notgate) — last, so
         a fuzzy dataset hit never shadows an explicitly named fixture.
    """
    if nl_override:
        return {
            "task_id": module_name,
            "module_name": module_name,
            "nl_description": pathlib.Path(nl_override).read_text(),
            "golden_dut": (
                pathlib.Path(dut_override).read_text() if dut_override else ""
            ),
        }

    # Exact VerilogEval match (e.g. "Prob005_notgate")
    prompt_path = _VERILOG_EVAL_DIR / f"{module_name}_prompt.txt"
    ref_path = _VERILOG_EVAL_DIR / f"{module_name}_ref.sv"
    if prompt_path.exists() and ref_path.exists():
        return {
            "task_id": module_name,
            "module_name": "RefModule",
            "nl_description": prompt_path.read_text(),
            "golden_dut": ref_path.read_text(),
        }

    # CMB / SEQ fixtures (before the fuzzy VerilogEval glob, so an explicit
    # fixture name like "mux2to1"/"dff" is never shadowed by a substring match)
    for fixture_dir in [_FIXTURES_CMB, _FIXTURES_SEQ]:
        p = fixture_dir / f"{module_name}_prompt.txt"
        r = fixture_dir / f"{module_name}_ref.v"
        if p.exists() and r.exists():
            return {
                "task_id": module_name,
                "module_name": module_name,
                "nl_description": p.read_text(),
                "golden_dut": r.read_text(),
            }

    # Partial VerilogEval match (e.g. "notgate" → Prob005_notgate_prompt.txt)
    for candidate in sorted(_VERILOG_EVAL_DIR.glob(f"*{module_name}*_prompt.txt")):
        stem = candidate.stem.replace("_prompt", "")
        ref = candidate.parent / f"{stem}_ref.sv"
        if ref.exists():
            return {
                "task_id": stem,
                "module_name": "RefModule",
                "nl_description": candidate.read_text(),
                "golden_dut": ref.read_text(),
            }

    raise FileNotFoundError(
        f"Module '{module_name}' not found.\n"
        f"  Searched VerilogEval: {_VERILOG_EVAL_DIR}\n"
        f"  Searched fixtures:    {_FIXTURES_CMB}, {_FIXTURES_SEQ}\n"
        f"  Use --nl and --dut to provide files directly."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pipeline",
        description="LangGraph Verilog testbench generation pipeline",
    )
    subparsers = parser.add_subparsers(dest="command")

    run_p = subparsers.add_parser("run", help="Run pipeline on a single module")
    run_p.add_argument(
        "--module", required=True,
        help="VerilogEval key (e.g. Prob005_notgate) or fixture name (e.g. half_adder)",
    )
    run_p.add_argument(
        "--mode",
        choices=["baseline", "compiler_only", "pyverilog_only", "hybrid"],
        default="hybrid",
        help="Ablation mode (default: hybrid)",
    )
    run_p.add_argument("--nl", help="Path to .txt NL description (overrides dataset)")
    run_p.add_argument("--dut", help="Path to golden DUT .v/.sv file (overrides dataset)")
    run_p.add_argument("--run-id", dest="run_id", help="Run ID (8-char UUID generated if omitted)")

    args = parser.parse_args()

    if args.command != "run":
        parser.print_help()
        return

    # Lazy imports so --help works even without ANTHROPIC_API_KEY
    from pipeline.config import AblationMode, PipelineConfig
    from pipeline.graph import build_graph

    try:
        module_data = load_module(args.module, args.nl, args.dut)
    except FileNotFoundError as e:
        print(f"[pipeline] ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    run_id = args.run_id or str(uuid.uuid4())[:8]
    mode = AblationMode(args.mode)
    config = PipelineConfig(mode=mode)

    initial_state: dict = {
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
        "max_repair_iter": config.max_repair_iter,
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
        "run_started_at": __import__("time").monotonic(),
        "mode": mode.value,
        "llm_calls": [],
    }

    print(f"[pipeline] run_id={run_id}  module={args.module}  mode={args.mode}")
    graph = build_graph(config)
    final_state = graph.invoke(initial_state)

    # Prefer the persisted result (single source of truth) for the summary.
    from pipeline.reporting import print_run_summary
    result_path = _PROJECT_ROOT / "results" / f"{run_id}.json"
    try:
        import json
        result = json.loads(result_path.read_text())
    except (OSError, ValueError):
        result = dict(final_state)  # fallback to in-memory state

    print_run_summary(result)
    print(f"[pipeline] result=results/{run_id}.json")


if __name__ == "__main__":
    main()
