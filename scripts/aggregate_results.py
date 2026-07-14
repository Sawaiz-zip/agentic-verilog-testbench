"""
Back-compat wrapper — re-aggregate whatever is already in results/ into summary.json.
The implementation lives in pipeline/eval/aggregate.py (importable + unit-tested).
"""

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from pipeline.eval.aggregate import aggregate, print_summary_table


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Aggregate result JSONs into a summary")
    p.add_argument("--results-dir", default="results",
                   help="directory of per-run result JSONs (default: results)")
    args = p.parse_args()

    summary = aggregate(args.results_dir)
    print_summary_table(summary)
    print(json.dumps(summary, indent=2))
