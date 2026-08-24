"""
Ablation-study batch runner CLI.

Examples:
  python scripts/run_eval.py                          # 5 CMB fixtures × 5 modes = 25 runs
  python scripts/run_eval.py --modules seq-fixtures   # SEQ fixtures × 5 modes
  python scripts/run_eval.py --modules verilogeval:10 --yes   # 10 problems × 5 modes (opt-in)
  python scripts/run_eval.py --modes hybrid --modules half_adder
"""

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from pipeline.config import AblationMode
from pipeline.eval.aggregate import aggregate, print_summary_table
from pipeline.eval.harness import ALL_MODES, estimate_runs, resolve_modules, run_sweep


def main() -> None:
    p = argparse.ArgumentParser(prog="run_eval", description="Ablation batch runner")
    p.add_argument("--modules", nargs="+", default=["cmb-fixtures"],
                   help="preset (cmb-fixtures|smoke|seq-fixtures|verilogeval[:N]) or names")
    p.add_argument("--modes", nargs="+",
                   choices=[m.value for m in ALL_MODES], default=None,
                   help="ablation modes (default: all five)")
    p.add_argument("--limit", type=int, default=None, help="cap number of modules")
    p.add_argument("--yes", action="store_true", help="opt in to a large sweep")
    p.add_argument("--results-dir", default="results")
    p.add_argument("--no-aggregate", action="store_true")
    args = p.parse_args()

    # Resolve modules (a single preset keyword, or a list of names).
    if len(args.modules) == 1:
        modules = resolve_modules(args.modules[0])
    else:
        modules = resolve_modules(args.modules)

    modes = ([AblationMode(m) for m in args.modes] if args.modes else list(ALL_MODES))

    n = estimate_runs(modules, modes, args.limit)
    print(f"[run_eval] selection → {len(modules)} modules × {len(modes)} modes "
          f"= {n} runs (limit={args.limit}, opt_in={args.yes})")

    result = run_sweep(modules, modes, limit=args.limit, opt_in=args.yes,
                       results_dir=args.results_dir)
    if result["refused"]:
        sys.exit(2)

    print(f"[run_eval] completed {result['ran']} runs.")
    if result.get("aborted"):
        print(f"[run_eval] sweep aborted early ({result.get('reason')}) — "
              f"aggregating the {result['ran']} runs that completed.")

    if not args.no_aggregate:
        summary = aggregate(args.results_dir)
        print_summary_table(summary)

    if result.get("aborted"):
        sys.exit(3)


if __name__ == "__main__":
    main()
