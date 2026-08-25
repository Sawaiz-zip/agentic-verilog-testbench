#!/usr/bin/env python3
"""
Cross-sweep analysis: the numbers the results chapter cites.

Pools every recorded run across sweeps and reports, with confidence intervals
and significance tests rather than eyeballed differences:

  - Eval1 per mode with Wilson 95% intervals and pairwise Fisher exact tests
  - RQ1: structural vs semantic failure split, and a category breakdown
  - RQ2: how often static analysis fired on real generated testbenches
  - RQ4: cost (tokens, wall time) against quality per mode
  - the measured variance floor, from arms that took an identical code path

Usage:
  python scripts/analyse_results.py results/final_hard_r1 results/weak_model_r1 ...
  python scripts/analyse_results.py --all
"""

import argparse
import collections
import glob
import itertools
import json
import math
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

_ROOT = pathlib.Path(__file__).parent.parent
MODES = ["baseline", "retry_only", "compiler_only", "pyverilog_only", "hybrid"]

# Keyword buckets for the failing-scenario taxonomy (RQ1). Deliberately coarse:
# scenario names are model-generated free text, so this indicates the shape of
# the failures, not a hand-verified classification.
CATEGORIES = [
    ("reset / initialisation", r"reset|init|startup|clear"),
    ("timing / clocking",      r"clock|cycle|timing|delay|posedge|edge|wait"),
    ("boundary / overflow",    r"boundary|overflow|underflow|wrap|max|min|full|empty|edge_case"),
    ("sequence / FSM state",   r"sequence|transition|state|detect|overlap|consecutive|multiple"),
    ("arithmetic / logic",     r"add|sub|shift|arith|signed|increment|count|compare|logic"),
    ("idle / hold",            r"no_activity|idle|hold|stable|nochange"),
]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval — behaves sensibly at small n, unlike normal approx."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def fisher_exact(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact p-value for [[a, b], [c, d]].

    Used instead of chi-square because per-mode counts are small (n=44) and
    several cells fall below the chi-square validity threshold.
    """
    n = a + b + c + d
    row1, row2, col1 = a + b, c + d, a + c
    if min(row1, row2, col1, n - col1) < 0 or n == 0:
        return 1.0

    def prob(x: int) -> float:
        return math.comb(row1, x) * math.comb(row2, col1 - x) / math.comb(n, col1)

    p_obs = prob(a)
    total = 0.0
    for x in range(max(0, col1 - row2), min(row1, col1) + 1):
        px = prob(x)
        if px <= p_obs + 1e-12:
            total += px
    return min(1.0, total)


def load(dirs: list[str]) -> list[dict]:
    """Newest record per (sweep, task_id, mode)."""
    best: dict[tuple, tuple] = {}
    for d in dirs:
        tag = pathlib.Path(d).name
        for path in glob.glob(str(pathlib.Path(d) / "*.json")):
            if path.endswith("summary.json"):
                continue
            try:
                rec = json.loads(pathlib.Path(path).read_text())
            except (json.JSONDecodeError, OSError):
                continue
            if not rec.get("mode"):
                continue
            rec["_sweep"] = tag
            key = (tag, rec.get("task_id") or rec.get("module_name"), rec["mode"])
            mt = pathlib.Path(path).stat().st_mtime
            if key not in best or mt > best[key][0]:
                best[key] = (mt, rec)
    return [r for _, r in best.values()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="*")
    ap.add_argument("--all", action="store_true",
                    help="use every results dir containing mode-tagged records")
    args = ap.parse_args()

    dirs = args.dirs
    if args.all or not dirs:
        dirs = sorted(
            str(p) for p in (_ROOT / "results").iterdir()
            if p.is_dir() and any(
                "mode" in (pathlib.Path(f).read_text()[:400])
                for f in glob.glob(str(p / "*.json"))[:3]
            )
        )

    recs = load(dirs)
    if not recs:
        print("no mode-tagged records found")
        raise SystemExit(1)

    sweeps = collections.Counter(r["_sweep"] for r in recs)
    print("=" * 78)
    print("CROSS-SWEEP ANALYSIS")
    print("=" * 78)
    print(f"\nRuns: {len(recs)} across {len(sweeps)} sweeps")
    for s, n in sweeps.most_common():
        print(f"  {s:26} {n:4d}")

    # ── Eval1 with intervals ────────────────────────────────────────────────
    print("\n\n## Eval1 by mode, pooled, with 95% Wilson intervals\n")
    print(f"  {'mode':16}{'pass/n':>10}{'rate':>9}{'95% CI':>20}")
    stats: dict[str, tuple[int, int]] = {}
    for m in MODES:
        rs = [r for r in recs if r["mode"] == m]
        if not rs:
            continue
        k, n = sum(1 for r in rs if r["eval1_pass"]), len(rs)
        stats[m] = (k, n)
        lo, hi = wilson(k, n)
        print(f"  {m:16}{f'{k}/{n}':>10}{100*k/n:>8.1f}%"
              f"{f'[{100*lo:.1f}, {100*hi:.1f}]':>20}")

    print("\n## Pairwise Fisher exact tests\n")
    any_sig = False
    for a, b in itertools.combinations([m for m in MODES if m in stats], 2):
        ka, na = stats[a]; kb, nb = stats[b]
        p = fisher_exact(ka, na - ka, kb, nb - kb)
        flag = "SIGNIFICANT" if p < 0.05 else ("marginal" if p < 0.10 else "")
        any_sig |= p < 0.05
        print(f"  {a:16} vs {b:16} p={p:.3f}  {flag}")
    if not any_sig:
        print("\n  No pairwise difference reaches p<0.05. Reported gaps are not"
              "\n  distinguishable from sampling variation at this sample size.")

    # ── Variance floor ──────────────────────────────────────────────────────
    print("\n\n## Measured variance floor\n")
    print("  Arms that performed zero repairs took an identical code path, so any"
          "\n  difference between them is pure sampling variation.\n")
    for s in sweeps:
        sub = [r for r in recs if r["_sweep"] == s]
        zero = [m for m in MODES
                if sub and sum(r["repair_iter"] for r in sub if r["mode"] == m) == 0
                and any(r["mode"] == m for r in sub)]
        vals = []
        for m in zero:
            rs = [r for r in sub if r["mode"] == m]
            vals.append((m, 100 * sum(1 for r in rs if r["eval1_pass"]) / len(rs)))
        if len(vals) > 1:
            spread = max(v for _, v in vals) - min(v for _, v in vals)
            print(f"  {s:26} " + ", ".join(f"{m}={v:.0f}%" for m, v in vals)
                  + f"  -> spread {spread:.0f} pts")

    # ── RQ1 ─────────────────────────────────────────────────────────────────
    print("\n\n## RQ1 — where failures actually originate\n")
    nocomp = [r for r in recs if not r["eval0_pass"]]
    simfail = [r for r in recs if r["eval0_pass"] and not r["eval1_pass"]]
    passed = len(recs) - len(nocomp) - len(simfail)
    print(f"  failed to compile (structural/syntactic) : {len(nocomp):4d}")
    print(f"  compiled, failed simulation (SEMANTIC)   : {len(simfail):4d}")
    print(f"  passed                                   : {passed:4d}")
    if len(nocomp) + len(simfail):
        share = 100 * len(simfail) / (len(nocomp) + len(simfail))
        print(f"\n  -> {share:.0f}% of failures are semantic, i.e. invisible without simulation")

    names = [s["name"] for r in simfail
             for s in (r.get("scenario_results") or []) if not s.get("passed")]
    counts = collections.Counter()
    unc = 0
    for nm in names:
        for lab, pat in CATEGORIES:
            if re.search(pat, nm, re.I):
                counts[lab] += 1
                break
        else:
            unc += 1
    print(f"\n  {len(names)} failing scenarios, by keyword category:")
    for lab, c in counts.most_common():
        print(f"    {c:5d}  {lab}")
    print(f"    {unc:5d}  uncategorised")

    # ── RQ2 ─────────────────────────────────────────────────────────────────
    print("\n\n## RQ2 — did static analysis fire on real generated testbenches?\n")
    for s in list(sweeps) + ["ALL"]:
        sub = recs if s == "ALL" else [r for r in recs if r["_sweep"] == s]
        passes = types = 0
        pf = 0
        hits = 0
        tc = collections.Counter()
        for r in sub:
            found = False
            for f in (r.get("static_findings") or []):
                passes += 1
                if not f.get("parse_ok"):
                    pf += 1
                ts = f.get("error_types") or []
                tc.update(ts)
                found |= bool(ts)
            hits += int(found)
        print(f"  {s:26} analyses={passes:4d}  parse_fail={pf:2d}  "
              f"runs_with_findings={hits:3d}/{len(sub):3d}  {dict(tc) or '{}'}")

    # ── RQ4 ─────────────────────────────────────────────────────────────────
    print("\n\n## RQ4 — cost against quality\n")
    print(f"  {'mode':16}{'n':>5}{'tok_in':>10}{'tok_out':>10}{'wall_s':>9}"
          f"{'Eval1':>8}{'vs base':>10}")
    base = None
    for m in MODES:
        rs = [r for r in recs if r["mode"] == m]
        if not rs:
            continue
        ti = sum(r["tokens_in_total"] for r in rs) / len(rs)
        to = sum(r["tokens_out_total"] for r in rs) / len(rs)
        w = sum(r["wall_clock_ms"] for r in rs) / len(rs) / 1000
        e1 = 100 * sum(1 for r in rs if r["eval1_pass"]) / len(rs)
        if m == "baseline":
            base = (ti + to, e1)
        rel = ""
        if base and m != "baseline":
            rel = f"{100*((ti+to)/base[0]-1):+.0f}% tok"
        print(f"  {m:16}{len(rs):>5}{ti:>10,.0f}{to:>10,.0f}{w:>9.0f}{e1:>7.1f}%{rel:>10}")

    print()


if __name__ == "__main__":
    main()
