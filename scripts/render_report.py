#!/usr/bin/env python3
"""
Render a sweep's result records as a readable Markdown report.

The JSON records stay the source of truth — the aggregator, the repeat
aggregator and the injection study's corpus loader all read them, and keeping
them means a different table can be produced later without re-running a sweep
that costs real money. This adds a human-readable view on top; it never
modifies or replaces the data.

Usage:
  python scripts/render_report.py results/final_hard_r1
  python scripts/render_report.py results/final_hard_r1 results/final_hard_r2
  python scripts/render_report.py results/final_hard_r1 -o docs/results/repeat-1.md
"""

import argparse
import collections
import glob
import json
import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from pipeline.eval.aggregate import aggregate
from pipeline.eval.harness import ALL_MODES

MODE_ORDER = [m.value for m in ALL_MODES]


def load_records(results_dir: str) -> list[dict]:
    """Newest record per (task_id, mode) — the same de-duplication the aggregator uses."""
    best: dict[tuple, tuple] = {}
    for path in glob.glob(str(pathlib.Path(results_dir) / "*.json")):
        if path.endswith("summary.json"):
            continue
        try:
            rec = json.loads(pathlib.Path(path).read_text())
        except (json.JSONDecodeError, OSError):
            continue
        key = (rec.get("task_id") or rec.get("module_name"), rec.get("mode"))
        mtime = pathlib.Path(path).stat().st_mtime
        if key not in best or mtime > best[key][0]:
            best[key] = (mtime, rec)
    return [r for _, r in best.values()]


def _pct(x) -> str:
    return f"{100 * x:.0f}%" if isinstance(x, (int, float)) else "—"


def _mark(rec: dict) -> str:
    """One cell of the circuit x mode matrix."""
    if rec is None:
        return "·"
    if rec.get("final_status") == "harness_error":
        return "ERR"
    ok = rec.get("eval1_pass")
    reps = rec.get("repair_iter", 0)
    return ("✅" if ok else "❌") + (f"{reps}" if reps else "")


def render(dirs: list[str]) -> str:
    out: list[str] = []
    all_records: list[dict] = []
    for d in dirs:
        all_records.extend(load_records(d))

    if not all_records:
        return "No result records found.\n"

    circuits = sorted({r.get("task_id") or r.get("module_name") for r in all_records})
    modes = [m for m in MODE_ORDER if any(r.get("mode") == m for r in all_records)]
    ctype = {r.get("task_id") or r.get("module_name"): r.get("circuit_type", "")
             for r in all_records}

    title = "Evaluation Sweep" + (" (combined)" if len(dirs) > 1 else "")
    out.append(f"# {title}\n")
    out.append(f"**Source:** {', '.join(f'`{d}`' for d in dirs)}  ")
    out.append(f"**Circuits:** {len(circuits)}  ·  **Modes:** {len(modes)}  "
               f"·  **Records:** {len(all_records)}\n")

    temps = sorted({c.get("temperature") for r in all_records
                    for c in (r.get("llm_calls") or []) if c.get("temperature") is not None})
    models = sorted({c.get("model") for r in all_records
                     for c in (r.get("llm_calls") or []) if c.get("model")})
    if temps:
        out.append(f"**Temperature:** {', '.join(str(t) for t in temps)}  ")
    if models:
        out.append(f"**Models:** {', '.join(f'`{m}`' for m in models)}\n")

    # ── Completeness ────────────────────────────────────────────────────────
    expected = len(circuits) * len(modes)
    errors = [r for r in all_records if r.get("final_status") == "harness_error"]
    out.append("\n## Completeness\n")
    out.append(f"- Runs recorded: **{len(all_records)} / {expected}** expected")
    if len(all_records) < expected:
        have = {(r.get("task_id") or r.get("module_name"), r.get("mode")) for r in all_records}
        missing = [f"{c} × {m}" for c in circuits for m in modes if (c, m) not in have]
        out.append(f"- **Missing:** {', '.join(missing)}")
    out.append(f"- Harness errors: **{len(errors)}**"
               + (f" ({', '.join(r.get('module_name','?') for r in errors)})" if errors else ""))

    # ── Per-mode summary ────────────────────────────────────────────────────
    out.append("\n## Results by mode\n")
    out.append("| mode | n | Eval0 | Eval1 | Eval2 | mean repairs | tokens in | tokens out | mean wall |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    summaries = {}
    for d in dirs:
        for mode, s in aggregate(d).items():
            summaries.setdefault(mode, []).append(s)
    for m in modes:
        ss = summaries.get(m, [])
        if not ss:
            continue
        def avg(key):
            vals = [s[key] for s in ss if key in s]
            return statistics.fmean(vals) if vals else 0.0
        n = sum(s["n"] for s in ss)
        out.append(
            f"| `{m}` | {n} | {_pct(avg('eval0_pass_rate'))} | {_pct(avg('eval1_pass_rate'))} "
            f"| {_pct(avg('eval2_pass_rate'))} | {avg('mean_repair_iter'):.2f} "
            f"| {avg('mean_tokens_in'):,.0f} | {avg('mean_tokens_out'):,.0f} "
            f"| {avg('mean_wall_clock_ms')/1000:.0f}s |"
        )

    out.append("\n> `retry_only` is the control arm: one extra generation with **no** "
               "diagnostics. A mode must beat it, not merely `baseline`, for its feedback "
               "to be doing the work.\n")

    # ── Circuit x mode matrix ───────────────────────────────────────────────
    out.append("\n## Per-circuit outcomes\n")
    out.append("✅ = Eval1 pass, ❌ = fail; the digit is the number of repair iterations used.\n")
    out.append("| circuit | type | " + " | ".join(f"`{m}`" for m in modes) + " |")
    out.append("|---|---|" + "---|" * len(modes))
    index = {(r.get("task_id") or r.get("module_name"), r.get("mode")): r for r in all_records}
    for c in circuits:
        cells = " | ".join(_mark(index.get((c, m))) for m in modes)
        out.append(f"| `{c}` | {ctype.get(c,'')} | {cells} |")

    # ── Where repairs came from ─────────────────────────────────────────────
    out.append("\n## Repair feedback sources\n")
    out.append("What actually triggered each repair — the mechanism behind any gain.\n")
    out.append("| mode | repairs | static | compile | simulation | none (control) |")
    out.append("|---|---|---|---|---|---|")
    for m in modes:
        srcs = collections.Counter(
            h.get("feedback_source", "?")
            for r in all_records if r.get("mode") == m
            for h in (r.get("repair_history") or [])
        )
        total = sum(srcs.values())
        out.append(f"| `{m}` | {total} | {srcs.get('static',0)} | {srcs.get('compile',0)} "
                   f"| {srcs.get('simulation',0)} | {srcs.get('none',0)} |")

    # ── Static analysis in the wild ─────────────────────────────────────────
    out.append("\n## Static findings on real generated testbenches\n")
    types = collections.Counter()
    parse_fail = 0
    passes = 0
    for r in all_records:
        for f in (r.get("static_findings") or []):
            passes += 1
            if not f.get("parse_ok"):
                parse_fail += 1
            types.update(f.get("error_types") or [])
    out.append(f"- Analysis passes: **{passes}**  ·  Pyverilog parse failures: **{parse_fail}**")
    if types:
        out.append("\n| finding | count |")
        out.append("|---|---|")
        for t, n in types.most_common():
            out.append(f"| `{t}` | {n} |")
    else:
        out.append("- **No structural findings.** The generated testbenches were "
                   "structurally clean; the defects that remained were behavioural, "
                   "which static analysis cannot see.")

    # ── Eval2 mutant validity ───────────────────────────────────────────────
    caught = sum(r.get("eval2_caught", 0) for r in all_records)
    valid = sum(r.get("eval2_valid_mutants", 0) for r in all_records)
    total_m = sum(r.get("eval2_total_mutants", 0) for r in all_records)
    if total_m:
        out.append("\n## Eval2 mutant quality\n")
        out.append(f"- Mutants generated: **{total_m}**  ·  compiled (valid): **{valid}**  "
                   f"·  caught: **{caught}**")
        out.append(f"- Invalid mutants excluded from scoring: **{total_m - valid}** "
                   f"({_pct((total_m - valid) / total_m)} of generated)")
        out.append("\n> A mutant that does not compile is a bad mutation, not a testbench "
                   "failure, so it is excluded from both numerator and denominator.")

    # ── Outcome distribution ────────────────────────────────────────────────
    out.append("\n## Final status distribution\n")
    out.append("| mode | " + " | ".join(sorted({r.get("final_status","?") for r in all_records})) + " |")
    statuses = sorted({r.get("final_status", "?") for r in all_records})
    out.append("|---|" + "---|" * len(statuses))
    for m in modes:
        c = collections.Counter(r.get("final_status","?") for r in all_records if r.get("mode")==m)
        out.append(f"| `{m}` | " + " | ".join(str(c.get(s,0)) for s in statuses) + " |")

    # ── Things worth a second look ──────────────────────────────────────────
    flags = []
    for r in all_records:
        name = f"{r.get('module_name')} × {r.get('mode')}"
        if r.get("final_status") == "oscillated":
            flags.append(f"`{name}` — oscillated (same error recurring)")
        if r.get("final_status") == "exhausted_iters":
            flags.append(f"`{name}` — used the full repair budget without passing")
        if not r.get("eval0_pass"):
            flags.append(f"`{name}` — did not compile")
        if r.get("eval1_pass") and r.get("eval2_pass_rate", 1) == 0:
            flags.append(f"`{name}` — passes Eval1 but catches no mutants (tests nothing)")
    if flags:
        out.append("\n## Worth a second look\n")
        for f in sorted(set(flags)):
            out.append(f"- {f}")

    out.append("")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+", help="one or more results directories")
    ap.add_argument("-o", "--out", default=None,
                    help="write here (default: <first dir>/REPORT.md)")
    args = ap.parse_args()

    md = render(args.dirs)
    out = pathlib.Path(args.out) if args.out else pathlib.Path(args.dirs[0]) / "REPORT.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md)
    print(md)
    print(f"\n[render_report] written → {out}")


if __name__ == "__main__":
    main()
