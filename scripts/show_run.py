#!/usr/bin/env python3
"""
Extract one run's artefacts as readable files, for inspection and diffing.

A result record stores the generated circuit and the final testbench as JSON
strings, which no Verilog tool will read and no human enjoys. This writes them
out as real files next to the golden reference, so they can be opened in an
editor or compared with `diff`.

It never modifies the record it reads.

Usage:
  python scripts/show_run.py --list                 # what runs exist
  python scripts/show_run.py --list --failed        # only the ones that failed
  python scripts/show_run.py d6bd8c0d               # extract one run
  python scripts/show_run.py d6bd8c0d -o /tmp/look  # extract somewhere specific

Writes into <out>/<run_id>/:
  generated_dut.v   the circuit the pipeline wrote for itself
  golden_dut.v      the reference circuit it was actually marked against
  testbench.v       the final testbench (best-so-far retained, post-repair)
  simulation.txt    what the simulator printed
  compiler.txt      compiler output, when compilation failed
  SUMMARY.md        what happened, and the diff-ready commands

Known limitation: intermediate testbench versions are not stored by the
pipeline. `repair_history` keeps the trigger and error signature per iteration,
but only the final retained testbench survives, so a before/after diff across
repair iterations cannot be reconstructed from these records.
"""

import argparse
import glob
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent.parent
SWEEPS = ["final_hard_r1", "weak_model_r1", "verilogeval_weak", "verilogeval_strong"]


def load_records() -> dict[str, tuple[dict, str]]:
    """Every run keyed by run_id, with the sweep it came from."""
    out: dict[str, tuple[dict, str]] = {}
    for sweep in SWEEPS:
        for path in glob.glob(str(ROOT / "results" / sweep / "*.json")):
            if path.endswith("summary.json"):
                continue
            try:
                rec = json.loads(pathlib.Path(path).read_text())
            except (OSError, json.JSONDecodeError):
                continue
            if rec.get("mode") and rec.get("run_id"):
                out[rec["run_id"]] = (rec, sweep)
    return out


def find_golden(rec: dict) -> tuple[str, str]:
    """The reference circuit this run was marked against. Returns (source, text)."""
    task = rec.get("task_id", "")

    ve = ROOT / "data" / "verilog_eval" / "problems" / f"{task}_ref.sv"
    if ve.exists():
        return str(ve.relative_to(ROOT)), ve.read_text()

    for kind in ("cmb", "seq"):
        fx = ROOT / "tests" / "fixtures" / kind / f"{task}_ref.v"
        if fx.exists():
            return str(fx.relative_to(ROOT)), fx.read_text()

    return "", ""


def cmd_list(records: dict, failed_only: bool, sweep_filter: str | None) -> None:
    rows = []
    for run_id, (rec, sweep) in records.items():
        if sweep_filter and sweep != sweep_filter:
            continue
        if failed_only and rec.get("eval1_pass"):
            continue
        rows.append((
            sweep, rec.get("task_id", "?"), rec.get("mode", "?"), run_id,
            "PASS" if rec.get("eval1_pass") else "fail",
            rec.get("final_status", "?"),
            rec.get("repair_iter", 0),
        ))
    rows.sort()

    print(f"{'sweep':<20} {'circuit':<28} {'mode':<15} {'run_id':<10} "
          f"{'eval1':<6} {'status':<17} rep")
    print("-" * 105)
    for r in rows:
        print(f"{r[0]:<20} {r[1]:<28} {r[2]:<15} {r[3]:<10} "
              f"{r[4]:<6} {r[5]:<17} {r[6]}")
    print(f"\n{len(rows)} runs")


def write(path: pathlib.Path, text: str) -> bool:
    """Write text if there is any; report whether a file was produced."""
    if not (text or "").strip():
        return False
    path.write_text(text if text.endswith("\n") else text + "\n")
    return True


def summary_md(rec: dict, sweep: str, golden_src: str, written: list[str]) -> str:
    rh = rec.get("repair_history") or []
    scen = rec.get("scenario_results") or []
    pv = rec.get("pyverilog_report") or {}
    findings = rec.get("static_findings") or []

    out = [
        f"# Run `{rec.get('run_id')}`",
        "",
        f"**Circuit:** `{rec.get('task_id')}`  ·  **Mode:** `{rec.get('mode')}`  "
        f"·  **Sweep:** `{sweep}`  ·  **Type:** {rec.get('circuit_type')}",
        "",
        "## Outcome",
        "",
        "| | |",
        "|---|---|",
        f"| Eval0 — compiles | {'✅ pass' if rec.get('eval0_pass') else '❌ fail'} |",
        f"| Eval1 — passes vs golden | {'✅ pass' if rec.get('eval1_pass') else '❌ fail'} |",
        f"| Eval2 — mutants caught | {rec.get('eval2_caught', 0)} / "
        f"{rec.get('eval2_valid_mutants', 0)} valid |",
        f"| Final status | `{rec.get('final_status')}` |",
        f"| Repair iterations | {rec.get('repair_iter', 0)} |",
        f"| Scenarios passed | {rec.get('scenarios_passed', 0)} / "
        f"{rec.get('scenarios_total', 0)} |",
        f"| Marked against | `{rec.get('eval_dut_source')}` DUT |",
        f"| Tokens | {rec.get('tokens_in_total', 0):,} in · "
        f"{rec.get('tokens_out_total', 0):,} out |",
        "",
    ]

    if scen:
        out += ["## Scenarios", ""]
        for s in scen:
            out.append(f"- {'✅' if s.get('passed') else '❌'} `{s.get('name', '?')}`")
        out.append("")

    out += [
        "## Static analysis",
        "",
        f"- Parser used: **{pv.get('parser_used', 'none')}**"
        + ("  ⚠️ Verible is syntax-only — none of the six structural checks ran."
           if pv.get("parser_used") == "verible" else ""),
        f"- Findings: **{len(findings)}**",
        "",
    ]
    for f in findings:
        if isinstance(f, dict):
            out.append(f"  - `{f.get('error_type', '?')}` on `{f.get('signal', '?')}`")

    if rh:
        out += ["", "## Repair history", ""]
        for r in rh:
            if not isinstance(r, dict):
                continue
            sig = (r.get("error_signature") or "").split("\n")[0][:100]
            out += [
                f"**Iteration {r.get('iteration', '?')}** — triggered by "
                f"`{r.get('feedback_source', '?')}`",
                "",
                f"> {sig}",
                "",
            ]
        out += [
            "> ⚠️ The testbench produced at each iteration is **not stored** — only the "
            "final retained version. A per-iteration code diff cannot be reconstructed.",
            "",
        ]

    out += ["## Files", ""]
    for name in written:
        out.append(f"- `{name}`")
    if golden_src:
        out += ["", f"Golden reference copied from `{golden_src}`."]

    out += [
        "",
        "## Compare",
        "",
        "```bash",
        "# what the pipeline designed vs the real circuit",
        "diff -u golden_dut.v generated_dut.v",
        "",
        "# re-run this testbench against the golden circuit",
        "iverilog -g2012 -o /tmp/rerun.out testbench.v golden_dut.v && vvp /tmp/rerun.out",
        "```",
        "",
    ]
    return "\n".join(out)


def cmd_show(records: dict, run_id: str, out_dir: pathlib.Path) -> int:
    match = [k for k in records if k.startswith(run_id)]
    if not match:
        print(f"No run matching '{run_id}'. Try --list.", file=sys.stderr)
        return 1
    if len(match) > 1:
        print(f"'{run_id}' is ambiguous: {', '.join(sorted(match))}", file=sys.stderr)
        return 1

    rec, sweep = records[match[0]]
    dest = out_dir / match[0]
    dest.mkdir(parents=True, exist_ok=True)

    golden_src, golden_text = find_golden(rec)

    written = []
    for name, text in [
        ("generated_dut.v", rec.get("dut_rtl", "")),
        ("golden_dut.v", golden_text),
        ("testbench.v", rec.get("driver_rtl", "")),
        ("simulation.txt", rec.get("sim_output", "")),
        ("compiler.txt", rec.get("compiler_output", "")),
    ]:
        if write(dest / name, text):
            written.append(name)

    (dest / "SUMMARY.md").write_text(summary_md(rec, sweep, golden_src, written))

    print(f"Run {match[0]}  ·  {rec.get('task_id')}  ·  {rec.get('mode')}  ·  {sweep}")
    print(f"  Eval0 {'pass' if rec.get('eval0_pass') else 'FAIL'}  "
          f"Eval1 {'pass' if rec.get('eval1_pass') else 'FAIL'}  "
          f"status {rec.get('final_status')}")
    print(f"\nWritten to {dest}/")
    for name in written + ["SUMMARY.md"]:
        print(f"  {name}")
    if golden_text and rec.get("dut_rtl"):
        print(f"\n  diff -u {dest}/golden_dut.v {dest}/generated_dut.v")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Extract one run's Verilog artefacts for inspection.")
    ap.add_argument("run_id", nargs="?", help="run id, or a unique prefix of one")
    ap.add_argument("--list", action="store_true", help="list runs instead")
    ap.add_argument("--failed", action="store_true", help="with --list: only Eval1 failures")
    ap.add_argument("--sweep", default=None, help="with --list: restrict to one sweep")
    ap.add_argument("-o", "--out", default=None,
                    help="output directory (default: results/inspect)")
    args = ap.parse_args()

    records = load_records()
    if not records:
        print("No result records found under results/.", file=sys.stderr)
        return 1

    if args.list or not args.run_id:
        cmd_list(records, args.failed, args.sweep)
        return 0

    out_dir = pathlib.Path(args.out) if args.out else ROOT / "results" / "inspect"
    return cmd_show(records, args.run_id, out_dir)


if __name__ == "__main__":
    sys.exit(main())
