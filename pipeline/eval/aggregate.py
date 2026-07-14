"""
Aggregate per-run result JSONs into a per-mode ablation summary.
Deterministic, no LLM, no API calls. RQ3 (repair effectiveness), RQ4 (cost),
plus the per-node failure-attribution contribution.
"""

import json
import os
from collections import defaultdict


def _load_records(results_dir: str) -> list[dict]:
    """Load result JSONs, skipping summary.json and any malformed file. Attaches
    the file mtime so callers can de-duplicate re-runs (newest wins)."""
    records = []
    if not os.path.isdir(results_dir):
        return records
    for fname in os.listdir(results_dir):
        if not fname.endswith(".json") or fname == "summary.json":
            continue
        path = os.path.join(results_dir, fname)
        try:
            with open(path) as f:
                rec = json.load(f)
            if not isinstance(rec, dict):
                continue
            rec["_mtime"] = os.path.getmtime(path)
            records.append(rec)
        except (OSError, ValueError):
            continue  # malformed / partial → skip
    return records


def _dedup_newest(records: list[dict]) -> list[dict]:
    """Keep the newest record per (task_id, mode) by file mtime. Uses task_id
    (logical circuit identity) rather than module_name, because every VerilogEval
    task shares module_name "RefModule" and would otherwise collapse into one.
    Falls back to module_name for older records written before task_id existed."""
    best: dict[tuple, dict] = {}
    for rec in records:
        ident = rec.get("task_id") or rec.get("module_name", "")
        key = (ident, rec.get("mode", "unknown"))
        cur = best.get(key)
        if cur is None or rec.get("_mtime", 0) > cur.get("_mtime", 0):
            best[key] = rec
    return list(best.values())


def _tokens(rec: dict, field_total: str, field_key: str) -> int:
    v = rec.get(field_total)
    if v is not None:
        return v
    return sum(c.get(field_key, 0) for c in rec.get("llm_calls", []))


def _mean(values: list) -> float:
    return (sum(values) / len(values)) if values else 0.0


def _distribution(records: list[dict], field: str, default: str) -> dict:
    counts: dict = defaultdict(int)
    for r in records:
        val = r.get(field)
        counts[str(val) if val else default] += 1
    n = len(records)
    return {
        k: {"count": c, "fraction": (c / n if n else 0.0)}
        for k, c in sorted(counts.items())
    }


def aggregate(results_dir: str = "results") -> dict:
    """Group de-duplicated result records by mode and compute the summary. Writes
    results/summary.json and returns the summary dict. Graceful on empty."""
    records = _dedup_newest(_load_records(results_dir))
    if not records:
        return {}

    by_mode: dict[str, list] = defaultdict(list)
    for rec in records:
        by_mode[rec.get("mode") or "unknown"].append(rec)

    summary: dict = {}
    for mode, runs in sorted(by_mode.items()):
        n = len(runs)
        summary[mode] = {
            "n": n,
            "eval0_pass_rate": _mean([bool(r.get("eval0_pass")) for r in runs]),
            "eval1_pass_rate": _mean([bool(r.get("eval1_pass")) for r in runs]),
            "eval2_pass_rate": _mean([r.get("eval2_pass_rate", 0.0) for r in runs]),
            "mean_repair_iter": _mean([r.get("repair_iter", 0) for r in runs]),
            "mean_tokens_in": _mean([_tokens(r, "tokens_in_total", "tokens_in") for r in runs]),
            "mean_tokens_out": _mean([_tokens(r, "tokens_out_total", "tokens_out") for r in runs]),
            "mean_wall_clock_ms": _mean([r.get("wall_clock_ms", 0) for r in runs]),
            "mean_scenarios_passed": _mean([r.get("scenarios_passed", 0) for r in runs]),
            "mean_scenarios_total": _mean([r.get("scenarios_total", 0) for r in runs]),
            "final_statuses": _distribution(runs, "final_status", "unknown"),
            "failure_stages": _distribution(runs, "failure_stage", "none"),
        }

    out_path = os.path.join(results_dir, "summary.json")
    try:
        with open(out_path, "w") as f:
            json.dump(summary, f, indent=2)
    except OSError:
        pass

    return summary


def print_summary_table(summary: dict) -> None:
    """Human-readable per-mode comparison table."""
    if not summary:
        print("No results to aggregate.")
        return

    line = "─" * 92
    print(line)
    print(f"{'mode':<16}{'n':>4}{'Eval0':>8}{'Eval1':>8}{'Eval2':>8}"
          f"{'repair':>8}{'tok_in':>10}{'tok_out':>9}{'wall_s':>9}")
    print(line)
    for mode, s in summary.items():
        print(f"{mode:<16}{s['n']:>4}"
              f"{s['eval0_pass_rate']:>8.0%}{s['eval1_pass_rate']:>8.0%}"
              f"{s['eval2_pass_rate']:>8.0%}{s['mean_repair_iter']:>8.2f}"
              f"{s['mean_tokens_in']:>10.0f}{s['mean_tokens_out']:>9.0f}"
              f"{s['mean_wall_clock_ms'] / 1000:>9.1f}")
    print(line)
    # Failure attribution + final-status breakdown per mode.
    for mode, s in summary.items():
        statuses = ", ".join(
            f"{k}={v['count']}" for k, v in s["final_statuses"].items()
        )
        stages = ", ".join(
            f"{k}={v['fraction']:.0%}" for k, v in s["failure_stages"].items()
        )
        print(f"  {mode}: status[{statuses}]")
        print(f"  {mode}: failure_stage[{stages}]")
    print(line)
