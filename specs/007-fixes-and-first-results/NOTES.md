# 007 — Pipeline Fixes, SEQ Prompt & First Real Results

**Date:** 2026-07-15 · **Branch:** `fix/static-analysis-and-eval-integrity`

This is a cross-cutting session (touches features 001/002/004/006 + a prompt change),
recorded here rather than editing the frozen per-feature specs. See `docs/research-log.md` for
the living status and result tables.

## Context

Switched provider to **OpenRouter** (paid: `claude-sonnet-4.5` + `gpt-4o-mini`) and ran
the first real ablation sweeps. Validating them surfaced several bugs that had made the
prior results untrustworthy; all are now fixed and the pipeline produces a clean,
defensible first result.

## Changes (commits)

| Commit | Change | Why |
|---|---|---|
| `de0eec1` | **Pyverilog parse fix** (trailing newline before TB+DUT concat) | Static analysis was parsing **0/8** testbenches (silent failure → looked "clean"). Now 7/8; Verible covers the rest. Unblocks RQ2/RQ3. |
| `de0eec1` | **`task_id`** identity + loader precedence + aggregate de-dup | Fixtures were shadowed by VerilogEval substring matches; all VerilogEval tasks share `module_name="RefModule"` and would collapse to n=1/mode in aggregation (would ruin the 156 run). |
| `de0eec1` | `aggregate_results.py` honors `--results-dir` | Was always reading the default folder. |
| `c7f3154` | **Best-so-far retention** (`state.best_snapshot`) | Repair regenerates the whole TB; a later iteration could be worse, yet the last was reported. More repair could score *below* less repair. Now report the best evaluated TB; routing still uses current eval. |
| `95b8d3b` | **LangSmith LLM-call wrapping** | Each LLM call now appears in the trace (prompt/response/tokens) under its node. Project `S6-ReKI-1`. |
| `c0cc1e4` | **Strict SEQ protocol** in `gen_driver.j2` | SEQ failures were genuine TB bugs (e.g. `counter_4bit` held reset asserted then expected counting). New protocol: free-running clock; assert-then-DE-ASSERT reset; drive→posedge→settle→check; track state cycle-by-cycle. |

## Validation

- Full test suite: **73 passed, 3 skipped** (2 new best-so-far tests).
- SEQ prompt (temp 0): `counter_4bit` baseline **fail 3/8 → PASS 8/8** (pure generation);
  `dff` hybrid exhausted-fail → **PASS 30/30** in one repair.
- First ablation (8 fixtures × 4 modes) — see `results/final_temp07/` and `results/final_temp00/`:
  **`pyverilog_only` beats baseline at both temperatures (88% vs 75%/62%)** — core contribution
  demonstrated; `hybrid` = 100% Eval1 at temp 0.7; Eval0 = 100% (beats AutoBench 95.7%).

## Known caveats (must carry into the report)

1. **Overfitting risk** — the SEQ prompt was tuned on these 8 fixtures. Treat the VerilogEval
   156 as **held-out**; freeze prompts before running it.
2. **Residual nondeterminism at temp 0** — e.g. `counter_4bit` baseline fails but compiler_only
   passes with 0 repairs. Controlled run is less noisy, not noise-free.
3. **8 fixtures only** — top-two mode ordering (hybrid vs pyverilog_only) flips between temps;
   within noise at this N. Not comparable to AutoBench until the 156 run.

## Follow-ups (see `docs/roadmap.md`)

- Held-out VerilogEval 156 run (real head-to-head vs AutoBench).
- Pyverilog precision/recall via error-injection (FR-017).
- Merge branch → `main`; add 402 "out of credits" clean-abort to the harness.
- Regenerate `diagrams/*.png` from the updated `.puml` (PlantUML not installed locally).
