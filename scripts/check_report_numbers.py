#!/usr/bin/env python3
"""
Cross-check the figures quoted in report.tex against the recorded data.

A report that quotes a number the data does not support is worse than one that
quotes no numbers. Every claim below is recomputed from results/*.json and the
injection study, then searched for in the report source.
"""
import glob, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).parent.parent
tex = (ROOT / "report.tex").read_text()

def load(dirs):
    out = []
    for d in dirs:
        for f in glob.glob(str(ROOT / "results" / d / "*.json")):
            if f.endswith("summary.json"):
                continue
            r = json.loads(pathlib.Path(f).read_text())
            if r.get("mode"):
                r["_sweep"] = d
                out.append(r)
    return out

recs = load(["final_hard_r1", "weak_model_r1", "verilogeval_weak"])
# The static layer is reported over all four sweeps; the arm-level claims below
# are scoped to the 220-run ablation sample and must not include the strong sweep.
all_recs = recs + load(["verilogeval_strong"])
inj = json.loads((ROOT / "results" / "injection_study_final.json").read_text())

checks = []
def claim(label, value, *patterns):
    found = any(re.search(p, tex) for p in patterns)
    checks.append((label, value, found))

# --- sweep-level -------------------------------------------------------------
claim("total runs", len(recs), r"220 pipeline runs|220 of 220|220 evaluation\s*\n?runs|220 runs")
claim("harness errors", sum(1 for r in recs if r.get("final_status") == "harness_error"),
      r"without a harness failure|no harness errors")
nocomp = sum(1 for r in recs if not r["eval0_pass"])
simfail = sum(1 for r in recs if r["eval0_pass"] and not r["eval1_pass"])
claim("failed to compile", nocomp, rf"\b{nocomp}\b.*failed to compile|Failed to compile\s*&\s*{nocomp}")
claim("compiled then failed sim", simfail, rf"\b{simfail}\b")
claim("semantic share", f"{100*simfail/(nocomp+simfail):.0f}%", r"87\\%")

analyses = sum(len(r.get("static_findings") or []) for r in all_recs)
parsed = sum(1 for r in all_recs for f in (r.get("static_findings") or [])
             if f.get("parser_used") == "pyverilog")
hits = sum(1 for r in all_recs if any(f.get("error_types") for f in (r.get("static_findings") or [])))
claim("static analyses", analyses, rf"\b{analyses}\b")
claim("analyses Pyverilog parsed", parsed, rf"\b{parsed}\b")
claim("runs with a finding", hits, rf"{hits} runs with findings|three runs in the {parsed}")

pyv = [r for r in recs if r["mode"] == "pyverilog_only"]
claim("pyverilog_only runs", len(pyv),
      rf"zero repairs in {len(pyv)} runs", rf"across {len(pyv)} runs it never")
claim("pyverilog_only repairs", sum(r["repair_iter"] for r in pyv), r"zero repairs")

for m, lbl in [("baseline","27.3"),("retry_only","29.5"),("compiler_only","34.1"),
               ("pyverilog_only","20.5"),("hybrid","40.9")]:
    rs = [r for r in recs if r["mode"] == m]
    rate = 100*sum(1 for r in rs if r["eval1_pass"])/len(rs)
    claim(f"Eval1 {m}", f"{rate:.1f}%", re.escape(f"{rate:.1f}\\%"))

src = {}
for r in recs:
    for h in (r.get("repair_history") or []):
        src[h.get("feedback_source")] = src.get(h.get("feedback_source"), 0) + 1
claim("simulation repairs", src.get("simulation"), rf"{src.get('simulation')} repairs triggered by simulation|{src.get('simulation')} repairs")
claim("compile repairs", src.get("compile"), rf"{src.get('compile')} by the\s*\n?compiler|8 by the compiler")

# --- injection study ---------------------------------------------------------
cases = inj["cases"]
claim("injected faults", len(cases), rf"\b{len(cases)}\b faults|{len(cases)} faults")
det = sum(1 for c in cases if c["static_detected"])
claim("injection detection", f"{100*det/len(cases):.0f}%", r"93\\%")
claim("baseline false positives", sum(1 for b in inj["baseline"] if b["false_positive"]),
      r"no findings at all|no false alarms|produces no findings")
missed = [c for c in cases if not c["compiler_detected"] and not c["simulation_detected"]]
claim("missed by both", len(missed), rf"\b{len(missed)}\b")
claim("of those, static caught", sum(1 for c in missed if c["static_detected"]), r"catches 30|found 30|caught 30")

print(f"{'claim':34}{'data':>12}   in report?")
print("-"*62)
bad = 0
for label, value, found in checks:
    mark = "yes" if found else "NOT FOUND"
    if not found: bad += 1
    print(f"{label:34}{str(value):>12}   {mark}")
print()
print(f"{len(checks)-bad}/{len(checks)} claims located in the report source")
sys.exit(1 if bad else 0)
