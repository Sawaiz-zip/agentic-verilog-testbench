#!/usr/bin/env python3
"""
Error-injection study (FR-017, RQ1 + RQ2) — fully offline, spends ZERO tokens.

Takes every testbench already known to pass, injects one known fault at a time,
and records whether each of three layers notices:

    static      our Pyverilog analyser
    compiler    iverilog -g2012
    simulation  vvp against the golden DUT

Reports, per fault class, the detection rate of each layer plus the false-positive
rate on the unmutated testbenches. The column that matters for the thesis is
"static catches it, compiler and simulator do not" — those are faults the existing
tooling cannot find at all.

Usage:
  python scripts/run_injection_study.py
  python scripts/run_injection_study.py --out results/injection_study.json
  python scripts/run_injection_study.py --limit 5     # fewer source testbenches
"""

import argparse
import collections
import glob
import json
import pathlib
import sys

sys.stdout.reconfigure(line_buffering=True)

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from pipeline.analysis import fault_injection as fi
from pipeline.analysis import pyverilog_runner
from pipeline.eval import icarus

_ROOT = pathlib.Path(__file__).parent.parent


_FIXTURE_DIRS = [_ROOT / "tests" / "fixtures" / "cmb",
                 _ROOT / "tests" / "fixtures" / "seq"]


def _golden_dut(module_name: str) -> str | None:
    """The reference DUT for a circuit, from the fixtures.

    A recorded run stores `dut_rtl`, the DUT the pipeline *generated*, which may
    itself be malformed — evaluation used the golden DUT, not that one. Injecting
    into a testbench and then compiling it against a broken generated DUT would
    score the DUT's defects as if they were the injected fault.
    """
    for d in _FIXTURE_DIRS:
        path = d / f"{module_name}_ref.v"
        if path.exists():
            return path.read_text()
    return None


def load_corpus(limit: int | None = None) -> tuple[list[dict], list[dict]]:
    """Known-good (testbench, golden DUT) pairs, plus the entries rejected.

    Every entry is verified before use: the unmutated testbench must compile and
    its simulation must pass against the golden DUT. Anything that fails that gate
    is excluded and reported — measuring detection against a baseline that is
    already failing would attribute the baseline's problems to the injected fault.

    De-duplicated per circuit so one circuit with many recorded runs cannot
    dominate the statistics.
    """
    candidates: dict[str, dict] = {}
    for path in sorted(glob.glob(str(_ROOT / "results" / "**" / "*.json"), recursive=True)):
        if path.endswith("summary.json"):
            continue
        try:
            rec = json.loads(pathlib.Path(path).read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if not rec.get("eval1_pass") or not rec.get("driver_rtl"):
            continue
        name = rec.get("module_name")
        if not name or name in candidates:
            continue
        dut = _golden_dut(name) or rec.get("golden_dut")
        if not dut:
            continue
        candidates[name] = {
            "module_name": name,
            "circuit_type": rec.get("circuit_type", ""),
            "testbench": rec["driver_rtl"],
            "dut": dut,
        }

    corpus, rejected = [], []
    for entry in candidates.values():
        compiles, sim_passes = evaluate(entry["testbench"], entry["dut"])
        if compiles and sim_passes:
            corpus.append(entry)
        else:
            rejected.append({
                "module_name": entry["module_name"],
                "reason": "does not compile against the golden DUT" if not compiles
                          else "simulation fails against the golden DUT",
            })

    if limit:
        corpus = corpus[:limit]
    return corpus, rejected


def static_findings(tb: str, dut: str, module_name: str) -> list[tuple[str, str]]:
    report = pyverilog_runner.run(tb, dut, module_name=module_name)
    if not report.parse_ok:
        return [("parse_failed", "")]
    return [(e.error_type.value, e.affected_signal) for e in report.all_errors()]


def evaluate(tb: str, dut: str) -> tuple[bool, bool]:
    """(compiles, simulation_passes). A testbench that fails to compile cannot run."""
    ok, _out, path = icarus.compile_tb(tb, dut, timeout_s=30)
    if not ok:
        return False, False
    try:
        passed, _sim = icarus.simulate_tb(path, timeout_s=30)
    finally:
        p = pathlib.Path(path)
        if p.exists():
            p.unlink(missing_ok=True)
    return True, passed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/injection_study.json")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--report-only", action="store_true",
                    help="re-render the tables from a saved run, without re-running it")
    args = ap.parse_args()

    if args.report_only:
        saved = json.loads((_ROOT / args.out).read_text())
        report(saved["baseline"], saved["cases"])
        return

    corpus, rejected = load_corpus(args.limit)
    if not corpus:
        print("[injection] no verified-clean testbenches found — run a sweep first")
        raise SystemExit(1)

    print(f"[injection] corpus: {len(corpus)} verified-clean testbenches "
          f"({', '.join(c['module_name'] for c in corpus)})")
    if rejected:
        print(f"[injection] excluded {len(rejected)} recorded-passing testbenches that "
              f"do not reproduce against the golden DUT:")
        for r in rejected:
            print(f"    - {r['module_name']}: {r['reason']}")

    baseline = []
    cases = []

    for entry in corpus:
        tb, dut, name = entry["testbench"], entry["dut"], entry["module_name"]

        # Baseline: the unmutated testbench. Any finding here is a false positive.
        found = static_findings(tb, dut, name)
        baseline.append({
            "module_name": name,
            "circuit_type": entry["circuit_type"],
            "findings": found,
            "false_positive": bool([f for f in found if f[0] != "parse_failed"]),
            "parse_ok": not any(f[0] == "parse_failed" for f in found),
        })

        faults = fi.inject_all(tb, dut, name)
        print(f"  {name:24} {len(faults):3d} faults injectable")

        for fault in faults:
            found = static_findings(fault.testbench, dut, name)
            compiles, sim_passes = evaluate(fault.testbench, dut)
            types = {t for t, _ in found}
            cases.append({
                "module_name": name,
                "circuit_type": entry["circuit_type"],
                "kind": fault.kind,
                "expected_type": fault.expected_type,
                "signal": fault.signal,
                "description": fault.description,
                "static_findings": found,
                # Detected by the exact expected class...
                "static_detected": fault.expected_type in types,
                # ...or flagged at all (still useful: the repair loop gets a hint).
                "static_any": bool(types - {"parse_failed"}),
                "static_localised": any(
                    t == fault.expected_type and fault.signal.split("/")[0] in (s or "")
                    for t, s in found
                ),
                "compiler_detected": not compiles,
                "simulation_detected": compiles and not sim_passes,
            })

    out_path = _ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(
        {"baseline": baseline, "cases": cases, "excluded": rejected}, indent=2
    ))

    report(baseline, cases)
    print(f"\n[injection] raw data → {args.out}")


def report(baseline: list[dict], cases: list[dict]) -> None:
    print("\n" + "=" * 78)
    print("ERROR-INJECTION STUDY — detection by layer")
    print("=" * 78)

    fp = sum(1 for b in baseline if b["false_positive"])
    parse_ok = sum(1 for b in baseline if b["parse_ok"])
    print(f"\nBaseline (unmutated, all known to pass): {len(baseline)} testbenches")
    print(f"  Pyverilog parsed          : {parse_ok}/{len(baseline)}")
    print(f"  False positives           : {fp}/{len(baseline)}"
          f"  → precision on clean input {100 * (1 - fp / len(baseline)):.0f}%")
    for b in baseline:
        if b["false_positive"]:
            print(f"     ! {b['module_name']}: {b['findings']}")

    by_kind: dict[str, list[dict]] = collections.defaultdict(list)
    for c in cases:
        by_kind[c["kind"]].append(c)

    print(f"\nInjected faults: {len(cases)}\n")
    hdr = (f"{'fault class':24}{'n':>4}{'static':>9}{'compiler':>10}"
           f"{'sim':>7}{'ONLY static':>13}")
    print(hdr)
    print("-" * len(hdr))

    def pct(num, den):
        return f"{100 * num / den:.0f}%" if den else "n/a"

    total_only = 0
    for kind in sorted(by_kind):
        group = by_kind[kind]
        n = len(group)
        s = sum(1 for c in group if c["static_detected"])
        cm = sum(1 for c in group if c["compiler_detected"])
        sim = sum(1 for c in group if c["simulation_detected"])
        only = sum(1 for c in group
                   if c["static_detected"]
                   and not c["compiler_detected"] and not c["simulation_detected"])
        total_only += only
        print(f"{kind:24}{n:>4}{pct(s, n):>9}{pct(cm, n):>10}"
              f"{pct(sim, n):>7}{pct(only, n):>13}")

    n = len(cases)
    s = sum(1 for c in cases if c["static_detected"])
    cm = sum(1 for c in cases if c["compiler_detected"])
    sim = sum(1 for c in cases if c["simulation_detected"])
    caught_by_existing = sum(1 for c in cases
                             if c["compiler_detected"] or c["simulation_detected"])
    print("-" * len(hdr))
    print(f"{'TOTAL':24}{n:>4}{pct(s, n):>9}{pct(cm, n):>10}"
          f"{pct(sim, n):>7}{pct(total_only, n):>13}")

    print(f"\nMissed by compiler AND simulator : {n - caught_by_existing}/{n} "
          f"({pct(n - caught_by_existing, n)})")
    print(f"  ...of those, caught by static  : {total_only}"
          f"/{n - caught_by_existing} "
          f"({pct(total_only, n - caught_by_existing)})")

    localised = sum(1 for c in cases if c["static_localised"])
    print(f"\nLocalisation (right class AND right signal): {localised}/{n} "
          f"({pct(localised, n)})")

    dead = [k for k, g in by_kind.items()
            if not any(c["static_detected"] for c in g)]
    if dead:
        print(f"\nFault classes the static layer never caught: {', '.join(sorted(dead))}")


if __name__ == "__main__":
    main()
