#!/usr/bin/env python3
"""
Does the structural null survive being shown the golden design?

The localiser reads the design the pipeline generated; evaluation compiles
against the supplied golden design (report Section 8.1, fifth alternative
explanation). Every check tests agreement between two artefacts, and in
deployment those two were co-generated -- same model, same specification, same
run -- so agreement is partly guaranteed by construction.

This re-runs the frozen localiser over every stored testbench twice: once
paired with the generated design (reproducing deployment) and once paired with
the golden design (the condition the injection study actually validated).
Same testbenches, same checks, same code path; only the design differs.

Deterministic. No model calls.
"""
import glob, json, pathlib, sys, collections

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.analysis import pyverilog_runner

SWEEPS = ["final_hard_r1", "weak_model_r1", "verilogeval_weak", "verilogeval_strong"]


def goldens() -> dict[str, str]:
    out = {}
    for p in glob.glob(str(ROOT / "data/verilog_eval/problems/*_ref.sv")):
        out[pathlib.Path(p).stem.replace("_ref", "")] = pathlib.Path(p).read_text()
    for p in glob.glob(str(ROOT / "tests/fixtures/*/*_ref.v")):
        out[pathlib.Path(p).stem.replace("_ref", "")] = pathlib.Path(p).read_text()
    return out


def load_runs() -> list[dict]:
    runs = []
    for d in SWEEPS:
        for f in glob.glob(str(ROOT / "results" / d / "*.json")):
            if f.endswith("summary.json"):
                continue
            r = json.loads(pathlib.Path(f).read_text())
            if r.get("mode"):
                r["_sweep"] = d
                runs.append(r)
    return runs


def analyse(tb: str, dut: str, module: str) -> tuple[bool, list[str]]:
    rep = pyverilog_runner.run(tb, dut, module_name=module)
    d = rep.to_dict() if hasattr(rep, "to_dict") else dict(rep)
    kinds = [e["error_type"] for k in
             ("port_errors", "clock_errors", "dataflow_errors", "fdisplay_missing")
             for e in (d.get(k) or [])]
    return bool(d.get("parse_ok")), kinds


def main() -> None:
    G = goldens()
    runs = load_runs()
    rows = []
    for i, r in enumerate(runs, 1):
        tb, module, task = r["driver_rtl"], r.get("module_name", ""), r["task_id"]
        gen_ok, gen_f = analyse(tb, r.get("dut_rtl") or "", module)
        gol_ok, gol_f = analyse(tb, G[task], module)
        rows.append({"run_id": r.get("run_id"), "task_id": task, "sweep": r["_sweep"],
                     "mode": r["mode"], "eval1_pass": r.get("eval1_pass"),
                     "generated": {"parse_ok": gen_ok, "findings": gen_f},
                     "golden": {"parse_ok": gol_ok, "findings": gol_f}})
        print(f"\r  {i}/{len(runs)}", end="", flush=True)
    print()

    out = ROOT / "results" / "golden_reanalysis.json"
    out.write_text(json.dumps(rows, indent=2))

    def tally(arm):
        p = sum(1 for x in rows if x[arm]["parse_ok"])
        f = sum(1 for x in rows if x[arm]["findings"])
        return p, f

    gp, gf = tally("generated")
    op, of = tally("golden")
    n = len(rows)
    print(f"\n{'':22s} {'parsed':>12s} {'runs w/ finding':>18s}")
    print(f"  {'generated design':20s} {gp:>5d}/{n:<6d} {gf:>10d}")
    print(f"  {'golden design':20s} {op:>5d}/{n:<6d} {of:>10d}")

    both = [x for x in rows if x["generated"]["parse_ok"] and x["golden"]["parse_ok"]]
    disc_g = [x for x in both if x["golden"]["findings"] and not x["generated"]["findings"]]
    disc_o = [x for x in both if x["generated"]["findings"] and not x["golden"]["findings"]]
    print(f"\n  both parsed: {len(both)}")
    print(f"  finding ONLY against golden    : {len(disc_g)}")
    print(f"  finding ONLY against generated : {len(disc_o)}")

    c = collections.Counter(k for x in rows for k in x["golden"]["findings"])
    if c:
        print("\n  findings by class (golden arm):")
        for k, v in c.most_common():
            print(f"    {k:28s} {v}")
    print(f"\n  written: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
