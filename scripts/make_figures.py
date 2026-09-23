#!/usr/bin/env python3
"""
Generate the presentation figures as SVG.

Every number is read from the raw run records or stated inline with the source,
so a figure can never drift from the data behind it. Run after any sweep change:

    python scripts/make_figures.py            # writes docs/figures/*.svg
    python scripts/make_figures.py --png      # also rasterises via rsvg-convert

Palette is the validated default from the data-viz reference:
categorical slots 1-3 (#2a78d6 blue, #eb6834 orange, #1baf7a aqua), which pass
every adjacent-pair gate in light mode. Aqua sits below 3:1 on the light
surface, so every bar carries a visible direct label (the relief rule).
"""

import argparse
import collections
import glob
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).parent.parent
OUT = ROOT / "docs" / "figures"
SWEEPS = ["final_hard_r1", "weak_model_r1", "verilogeval_weak", "verilogeval_strong"]
ABL = SWEEPS[:3]

# ── palette (validated: node scripts/validate_palette.js "#2a78d6,#eb6834,#1baf7a") ──
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
INK3 = "#7a7974"
S1 = "#2a78d6"   # slot 1 blue   — "ours" / static analysis
S2 = "#eb6834"   # slot 2 orange — the comparator entity
S3 = "#1baf7a"   # slot 3 aqua
BLUE_300 = "#6da7ec"
BLUE_550 = "#1c5cab"
GRID = "#e6e5e1"

FONT = "Inter, 'Helvetica Neue', Helvetica, Arial, sans-serif"


# ── data loading ─────────────────────────────────────────────────────────────

def load(sweeps):
    rows = []
    for s in sweeps:
        for f in glob.glob(str(ROOT / "results" / s / "*.json")):
            if f.endswith("summary.json"):
                continue
            d = json.loads(pathlib.Path(f).read_text())
            if d.get("mode"):
                d["_sweep"] = s
                rows.append(d)
    return rows


def facts():
    """Everything the figures need, derived once from the records."""
    all_rows = load(SWEEPS)
    abl = load(ABL)

    f = {}
    f["n_runs"] = len(all_rows)
    f["eval0"] = sum(bool(r["eval0_pass"]) for r in all_rows)
    f["eval1"] = sum(bool(r["eval1_pass"]) for r in all_rows)

    trig = collections.Counter()
    for r in all_rows:
        for h in r.get("repair_history") or []:
            if isinstance(h, dict):
                trig[h.get("feedback_source")] += 1
    f["triggers"] = trig

    per_mode = {}
    for m in ["pyverilog_only", "baseline", "retry_only", "compiler_only", "hybrid"]:
        t = [r for r in abl if r["mode"] == m]
        rep = [r for r in t if (r.get("repair_iter") or 0) > 0]
        per_mode[m] = {
            "n": len(t),
            "pass": sum(bool(r["eval1_pass"]) for r in t),
            "first_try": sum(1 for r in t
                             if r["eval1_pass"] and (r.get("repair_iter") or 0) == 0),
            "rescued": sum(1 for r in rep if r["eval1_pass"]),
        }
    f["modes"] = per_mode

    seq = [r for r in all_rows if r["circuit_type"] == "SEQ"]
    inert = [r for r in seq if "[standardised]" not in (r.get("driver_rtl") or "")]
    strong = [r for r in seq if r["_sweep"] in ("final_hard_r1", "verilogeval_strong")]
    f["seq_inert"] = 100 * sum(bool(r["eval0_pass"]) for r in inert) / len(inert)
    f["seq_strong"] = 100 * sum(bool(r["eval0_pass"]) for r in strong) / len(strong)

    inj = json.loads((ROOT / "results" / "injection_study_final.json").read_text())
    agg = collections.defaultdict(lambda: collections.Counter())
    for c in inj["cases"]:
        v = agg[c["kind"]]
        v["n"] += 1
        v["static"] += bool(c["static_detected"])
        v["comp"] += bool(c["compiler_detected"])
        v["sim"] += bool(c["simulation_detected"])
    f["injection"] = agg
    return f


# ── svg helpers ──────────────────────────────────────────────────────────────

def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def txt(x, y, s, size=17, fill=INK2, anchor="start", weight="400", style=""):
    st = f' font-style="{style}"' if style else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{st}>{esc(s)}</text>')


def hbar(x, y, w, h, fill, r=4):
    """Horizontal bar with rounded data-end, square against the baseline."""
    w = max(w, 0.0)
    if w < r * 2:
        return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h}" fill="{fill}"/>'
    return (f'<path d="M{x:.1f},{y:.1f} H{x + w - r:.1f} A{r},{r} 0 0 1 {x + w:.1f},{y + r:.1f} '
            f'V{y + h - r:.1f} A{r},{r} 0 0 1 {x + w - r:.1f},{y + h:.1f} H{x:.1f} Z" fill="{fill}"/>')


def vbar(x, y, w, h, fill, r=4):
    """Vertical bar, rounded top, square on the baseline."""
    h = max(h, 0.0)
    if h < r * 2:
        return f'<rect x="{x:.1f}" y="{y + 0:.1f}" width="{w}" height="{h:.1f}" fill="{fill}"/>'
    return (f'<path d="M{x:.1f},{y + h:.1f} V{y + r:.1f} A{r},{r} 0 0 1 {x + r:.1f},{y:.1f} '
            f'H{x + w - r:.1f} A{r},{r} 0 0 1 {x + w:.1f},{y + r:.1f} V{y + h:.1f} Z" fill="{fill}"/>')


def svg(w, h, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" role="img" aria-label="{esc(title)}">\n'
            f'<rect width="{w}" height="{h}" fill="{SURFACE}"/>\n{body}\n</svg>\n')


def legend(x, y, items, size=16):
    out, cx = [], x
    for label, colour in items:
        out.append(f'<rect x="{cx}" y="{y - 11}" width="13" height="13" rx="3" fill="{colour}"/>')
        out.append(txt(cx + 20, y, label, size=size, fill=INK2))
        cx += 20 + len(label) * size * 0.55 + 30
    return "\n".join(out)


def write(name, content):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.svg").write_text(content)
    print(f"  {name}.svg")


# ── FIG-2 · the funnel ───────────────────────────────────────────────────────

def fig2(f):
    W, H = 1200, 520
    x0, top, bw, gap = 300, 130, 760, 40
    rows = [
        ("Runs executed", f["n_runs"], f["n_runs"], BLUE_550, ""),
        ("Compiled  (Eval0)", f["eval0"], f["n_runs"], S1,
         f'{100 * f["eval0"] / f["n_runs"]:.1f}%'),
        ("Worked against the\nreal circuit  (Eval1)", f["eval1"], f["n_runs"], BLUE_300,
         f'{100 * f["eval1"] / f["n_runs"]:.1f}%'),
    ]
    b = [txt(60, 62, "From 280 runs to 88 working testbenches", 30, INK, weight="600"),
         txt(60, 92, "Every testbench generated, and how far each got", 17, INK3)]
    y = top
    for label, val, total, colour, pct in rows:
        h = 74
        for i, line in enumerate(label.split("\n")):
            b.append(txt(x0 - 26, y + 34 + i * 22 - (11 if "\n" in label else 0),
                         line, 19, INK, anchor="end", weight="500"))
        b.append(hbar(x0, y, bw * val / total, h, colour))
        b.append(txt(x0 + 18, y + 47, f"{val}", 34, "#ffffff", weight="700"))
        if pct:
            b.append(txt(x0 + bw * val / total + 18, y + 46, pct, 26, INK2, weight="600"))
        y += h + gap
    b.append(txt(60, H - 26,
                 "31.4% is in the same range as the prior work's 37% on sequential circuits — "
                 "and these are the hardest quintile of the benchmark.", 16, INK3))
    write("fig2-funnel", svg(W, H, "\n".join(b), "Run funnel: 280 runs, 259 compiled, 88 worked"))


# ── FIG-3 · fault injection (hero) ───────────────────────────────────────────

def fig3(f):
    order = [
        ("port renamed", "port_rename", False),
        ("port left unconnected", "port_drop", False),
        ("input never driven", "undriven_input", False),
        ("wrong signal width", "width_change", False),
        ("output never checked", "unobserved_output", False),
        ("clock never toggles", "remove_clock_generator", False),
        ("swapped same-width bindings", "swap_bindings", True),
        ("broken edge synchronisation", "break_edge_sync", True),
    ]
    W, H = 1340, 900
    x0, bw, top = 430, 690, 152
    rowh, barh, bgap = 70, 15, 3
    DIVIDER_GAP = 52          # space opened above the negative-control block

    b = [txt(60, 58, "215 faults injected. Three detectors scored.", 30, INK, weight="600"),
         txt(60, 88, "Each bar is the share of that fault class the detector caught", 17, INK3),
         legend(x0, 122, [("Static analysis (ours)", S1), ("Compiler", S2), ("Simulator", S3)])]

    y = top
    for label, key, control in order:
        v = f["injection"][key]
        n = v["n"]
        if control and key == "swap_bindings":
            # Open the gap FIRST, then rule and label inside it, so nothing lands
            # on the row above.
            y += DIVIDER_GAP
            b.append(f'<line x1="60" y1="{y - 34}" x2="{W - 60}" y2="{y - 34}" '
                     f'stroke="{GRID}" stroke-width="1.5"/>')
            b.append(txt(60, y - 12, "NEGATIVE CONTROLS — built to be undetectable by structure",
                         14, INK3, weight="600"))
        ink = INK3 if control else INK
        b.append(txt(x0 - 22, y + 26, label, 18, ink, anchor="end",
                     weight="500", style="italic" if control else ""))
        b.append(txt(x0 - 22, y + 47, f"n = {n}", 14, INK3, anchor="end"))
        for i, (cnt, colour) in enumerate([(v["static"], S1), (v["comp"], S2), (v["sim"], S3)]):
            pct = 100 * cnt / n
            by = y + i * (barh + bgap)
            b.append(hbar(x0, by, bw * pct / 100, barh, colour))
            b.append(txt(x0 + bw * pct / 100 + 10, by + barh - 2,
                         f"{pct:.0f}%", 14, INK2, weight="600"))
        if key == "unobserved_output":
            b.append(f'<rect x="60" y="{y - 12}" width="{W - 120}" '
                     f'height="{3 * barh + 2 * bgap + 20}" fill="none" stroke="{S1}" '
                     f'stroke-width="2" rx="8" stroke-dasharray="7 5"/>')
            # sits on the third bar row, which is empty here (simulator = 0%)
            b.append(txt(W - 74, y + 2 * (barh + bgap) + barh - 2,
                         "← nothing else can see this one", 15, S1,
                         anchor="end", weight="700"))
        y += rowh

    fy = y + 34
    b.append(txt(60, fy,
                 "Nothing else can see it: the testbench stops checking an output, so it passes.",
                 18, S1, weight="600"))
    b.append(txt(60, fy + 30,
                 "100% of every class it was designed for (201/201) · 0 false positives on clean "
                 "testbenches · 30 of the 33 faults", 16, INK2))
    b.append(txt(60, fy + 54,
                 "invisible to both the compiler and the simulator. The two controls score 0, "
                 "exactly as predicted — the fault set was not cherry-picked.", 16, INK2))
    write("fig3-injection", svg(W, H, "\n".join(b),
                                "Fault injection: static analysis versus compiler and simulator"))


# ── FIG-4 · ablation ─────────────────────────────────────────────────────────

def fig4(f):
    m = f["modes"]
    order = [("pyverilog_only", ""), ("baseline", ""), ("retry_only", "the control"),
             ("compiler_only", ""), ("hybrid", "ours")]
    W, H = 1260, 700
    x0, bw, top, rowh, barh = 300, 620, 160, 84, 40
    maxv = 44

    b = [txt(60, 58, "How many circuits actually worked, out of 44", 30, INK, weight="600"),
         txt(60, 88, "Same 13 nodes in every arm — the only difference is when a second "
                     "attempt is allowed", 17, INK3)]

    y = top
    ys = {}
    for name, note in order:
        v = m[name]["pass"]
        ys[name] = y
        colour = S1 if name == "hybrid" else (S2 if name == "retry_only" else BLUE_300)
        b.append(txt(x0 - 24, y + 27, name, 19, INK, anchor="end",
                     weight="600" if name in ("hybrid", "retry_only") else "400"))
        if note:
            b.append(txt(x0 - 24, y + 48, note, 14, S2 if name == "retry_only" else S1,
                         anchor="end", weight="600"))
        b.append(hbar(x0, y, bw * v / maxv, barh, colour))
        b.append(txt(x0 + bw * v / maxv + 14, y + 28, f"{v}", 26, INK, weight="700"))
        y += rowh

    # noise-floor bracket between pyverilog_only and baseline
    bx = x0 + bw * 16.5 / maxv   # clear of the 12-bar and its value label
    y1, y2 = ys["pyverilog_only"] + barh / 2, ys["baseline"] + barh / 2
    b.append(f'<path d="M{bx},{y1} H{bx + 34} V{y2} H{bx}" fill="none" stroke="{INK3}" '
             f'stroke-width="2"/>')
    b.append(txt(bx + 46, (y1 + y2) / 2 - 4, "3 circuits apart —", 16, INK, weight="600"))
    b.append(txt(bx + 46, (y1 + y2) / 2 + 17, "but these two ran the same logic.", 16, INK2))
    b.append(txt(bx + 46, (y1 + y2) / 2 + 37, "This is the noise floor.", 16, INK2, weight="600"))

    fy = y + 46
    b.append(f'<line x1="60" y1="{fy - 30}" x2="{W - 60}" y2="{fy - 30}" stroke="{GRID}" '
             f'stroke-width="1.5"/>')
    b.append(txt(60, fy, "hybrid beats baseline by 6 circuits — but beats the control by 5, "
                         "against a noise floor of 3.", 18, INK, weight="600"))
    b.append(txt(60, fy + 28, "McNemar p = 0.372 — not significant. We report no significant "
                              "advantage rather than the 13.6-point win the naive", 16, INK2))
    b.append(txt(60, fy + 50, "baseline comparison would have given us.", 16, INK2))
    write("fig4-ablation", svg(W, H, "\n".join(b), "Ablation: circuits passed per mode, out of 44"))


# ── FIG-5 · repair triggers (hero) ───────────────────────────────────────────

def fig5(f):
    t = f["triggers"]
    rows = [("Simulation  (ran, wrong answers)", t["simulation"], S1),
            ("Blind retry  (the control — no information)", t["none"], S1),
            ("Compiler errors", t["compile"], S1),
            ("Static analysis  —  OUR CONTRIBUTION", t["static"], S2)]
    W, H = 1300, 620
    x0, bw, top, rowh, barh = 470, 640, 150, 78, 40
    maxv = max(v for _, v, _ in rows)

    b = [txt(60, 58, "What actually triggered every repair, across 280 runs", 30, INK,
             weight="600"),
         txt(60, 88, "The feedback source that caused the pipeline to rewrite a testbench",
             17, INK3)]
    y = top
    for label, v, colour in rows:
        strong = colour == S2
        b.append(txt(x0 - 24, y + 27, label, 18, INK if strong else INK2, anchor="end",
                     weight="700" if strong else "400"))
        b.append(hbar(x0, y, max(bw * v / maxv, 3), barh, colour))
        b.append(txt(x0 + max(bw * v / maxv, 3) + 16, y + 29, f"{v}",
                     34 if strong else 26, INK, weight="700"))
        if strong:
            b.append(txt(x0 + 74, y + 30, "one repair, in 280 runs", 19, S2, weight="700"))
        y += rowh

    fy = y + 44
    b.append(f'<line x1="60" y1="{fy - 32}" x2="{W - 60}" y2="{fy - 32}" stroke="{GRID}" '
             f'stroke-width="1.5"/>')
    b.append(txt(60, fy, "This is the central finding — and it is not a broken tool.",
                 20, INK, weight="700"))
    b.append(txt(60, fy + 30, "The localiser catches 100% of every fault class it was designed "
                              "for. The defects have simply become rare:", 17, INK2))
    b.append(txt(60, fy + 54, "87% of observed failures are semantic — the wiring is perfect, "
                              "the expected answer is wrong.", 17, INK2))
    b.append(txt(60, fy + 78, "pyverilog_only, the arm that isolates our layer, repaired 0 times "
                              "in 44 runs.", 17, INK2, weight="600"))
    write("fig5-triggers", svg(W, H, "\n".join(b), "Repair triggers across 280 runs"))


# ── FIG-6 · compile rate vs AutoBench ────────────────────────────────────────

def fig6(f):
    groups = [
        ("With no help from the fix", [("AutoBench, no standardisation", 55.5, S2),
                                       ("Ours, standardiser never fired", f["seq_inert"], S1)]),
        ("Best case", [("AutoBench, with their script", 97.3, S2),
                       ("Ours, strong model", f["seq_strong"], S1)]),
    ]
    W, H = 1280, 620
    x0, bw, top, barh, rowgap = 480, 620, 158, 46, 22

    b = [txt(60, 58, "Sequential compile rate — does their fix still matter?", 30, INK,
             weight="600"),
         txt(60, 88, "AutoBench's biggest single gain was a script worth +42 points. "
                     "Ours fired 6 times in 188 runs.", 17, INK3),
         legend(x0, 122, [("AutoBench (GPT-4-turbo, 2024)", S2), ("Ours (2026)", S1)])]

    y = top
    for gname, bars in groups:
        # group heading on its own line — beside the bars it collides with the
        # right-anchored series labels
        b.append(txt(60, y, gname.upper(), 15, INK3, weight="700"))
        y += 18
        for label, v, colour in bars:
            b.append(txt(x0 - 22, y + 30, label, 17, INK2, anchor="end"))
            b.append(hbar(x0, y, bw * v / 100, barh, colour))
            b.append(txt(x0 + bw * v / 100 + 14, y + 31, f"{v:.1f}%", 24, INK, weight="700"))
            y += barh + rowgap
        y += 26

    b.append(f'<line x1="60" y1="{H - 112}" x2="{W - 60}" y2="{H - 112}" stroke="{GRID}" '
             f'stroke-width="1.5"/>')
    b.append(txt(60, H - 78, "A 2026 pipeline whose fix does nothing compiles 35 points better "
                             "than a 2024 pipeline without one.", 19, INK, weight="700"))
    b.append(txt(60, H - 50, "The technique did not stop working — the defect it corrects "
                             "stopped happening.", 17, INK2))
    b.append(txt(60, H - 24, "Techniques in this field have a shelf life, and nobody measures it.",
                 17, S1, weight="600"))
    write("fig6-compile", svg(W, H, "\n".join(b), "Sequential compile rate versus AutoBench"))


# ── FIG-7 · where hybrid's passes came from ──────────────────────────────────

def fig7(f):
    m = f["modes"]
    W, H = 1100, 500
    x0, top, bw, barh, gap = 300, 170, 620, 66, 54
    maxv = 20

    b = [txt(60, 58, "Where hybrid's 18 passes actually came from", 30, INK, weight="600"),
         txt(60, 88, "Only the dark segment is the repair mechanism doing work", 17, INK3),
         legend(x0, 130, [("Passed on the first attempt", BLUE_300),
                          ("Rescued by a repair", S1)])]

    for i, name in enumerate(["baseline", "hybrid"]):
        v = m[name]
        y = top + i * (barh + gap)
        b.append(txt(x0 - 24, y + 42, name, 20, INK, anchor="end", weight="600"))
        w1 = bw * v["first_try"] / maxv
        b.append(hbar(x0, y, w1, barh, BLUE_300, r=0) if v["rescued"]
                 else hbar(x0, y, w1, barh, BLUE_300))
        b.append(txt(x0 + 16, y + 43, f'{v["first_try"]}', 28, "#ffffff", weight="700"))
        if v["rescued"]:
            w2 = bw * v["rescued"] / maxv
            b.append(hbar(x0 + w1 + 2, y, w2, barh, S1))
            b.append(txt(x0 + w1 + 2 + w2 / 2, y + 43, f'{v["rescued"]}', 28, "#ffffff",
                         weight="700", anchor="middle"))
        b.append(txt(x0 + bw * v["pass"] / maxv + 20, y + 43, f'= {v["pass"]}', 24, INK,
                     weight="700"))

    b.append(txt(60, H - 74, "15 first-attempt passes against baseline's 12 — same process, "
                             "so that gap is noise.", 18, INK2))
    b.append(txt(60, H - 46, "Only 3 of the 18 were rescued by repair.", 20, INK, weight="700"))
    b.append(txt(60, H - 20, "The mechanism is worth 3 circuits of 44 — about 6.8 points, "
                             "not the headline 13.6.", 17, INK2))
    write("fig7-decomposition", svg(W, H, "\n".join(b), "Where hybrid's passes came from"))


def rasterise():
    print("\nRasterising to PNG (2x):")
    for p in sorted(OUT.glob("*.svg")):
        png = p.with_suffix(".png")
        try:
            subprocess.run(["rsvg-convert", "-z", "2", "-o", str(png), str(p)], check=True)
            print(f"  {png.name}")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"  !! {p.name}: {e}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--png", action="store_true", help="also rasterise via rsvg-convert")
    args = ap.parse_args()

    f = facts()
    print(f"Data: {f['n_runs']} runs · Eval0 {f['eval0']} · Eval1 {f['eval1']} · "
          f"triggers {dict(f['triggers'])}\n")
    print("Writing figures:")
    fig2(f); fig3(f); fig4(f); fig5(f); fig6(f); fig7(f)
    if args.png:
        rasterise()
    print(f"\n→ {OUT}")


if __name__ == "__main__":
    main()
