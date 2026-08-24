"""
Aggregate several repeat sweeps into per-mode mean ± std (RQ3/RQ4).

Each results dir is one full (circuits × modes) sweep. With a stochastic
generator (temperature > 0), a single sweep is noisy; averaging over N repeats
and reporting the standard deviation gives defensible error bars.

Usage:
  python scripts/aggregate_repeats.py results/sweep_v3 results/sweep_rep2 results/sweep_rep3
"""

import statistics
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from pipeline.eval.aggregate import aggregate

MODES = ["baseline", "compiler_only", "pyverilog_only", "hybrid"]
METRICS = [
    ("eval0_pass_rate", "Eval0"),
    ("eval1_pass_rate", "Eval1"),
    ("eval2_pass_rate", "Eval2"),
    ("mean_repair_iter", "repair"),
    ("mean_tokens_in", "tok_in"),
    ("mean_tokens_out", "tok_out"),
]


def _mean_std(values):
    if not values:
        return 0.0, 0.0
    m = statistics.mean(values)
    s = statistics.stdev(values) if len(values) > 1 else 0.0
    return m, s


def main() -> None:
    dirs = sys.argv[1:]
    if len(dirs) < 2:
        print("Provide >= 2 results dirs (one per repeat sweep).")
        sys.exit(1)

    # per_mode[mode][metric] = [value_from_each_repeat]
    per_mode = {m: {k: [] for k, _ in METRICS} for m in MODES}
    for d in dirs:
        summ = aggregate(d)  # writes d/summary.json + returns per-mode dict
        for mode in MODES:
            s = summ.get(mode)
            if not s:
                continue
            for key, _ in METRICS:
                if key in s:
                    per_mode[mode][key].append(s[key])

    n = len(dirs)
    print(f"\nMean ± std over {n} repeat sweeps: {', '.join(dirs)}\n")
    line = "─" * 96
    print(line)
    hdr = f"{'mode':<16}"
    for _, label in METRICS:
        hdr += f"{label:>13}"
    print(hdr)
    print(line)
    for mode in MODES:
        row = f"{mode:<16}"
        for key, label in METRICS:
            vals = per_mode[mode][key]
            m, sd = _mean_std(vals)
            if key.startswith("eval"):
                row += f"{m*100:>6.0f}±{sd*100:<5.0f}"
            elif key == "mean_repair_iter":
                row += f"{m:>7.2f}±{sd:<4.2f}"
            else:
                row += f"{m:>7.0f}±{sd:<4.0f}"
        print(row)
    print(line)
    print("(Eval0/1/2 in %, mean±std across repeats; repair = mean iterations)\n")


if __name__ == "__main__":
    main()