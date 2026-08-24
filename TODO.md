# TODO — S6.ReKI.1

Living task list. Full context in `CLAUDE.md`; status/results in `PROGRESS.md`;
this session's write-up in `specs/008-control-arm-and-static-evidence/NOTES.md`.
Last updated: 2026-08-24.

## Scope decisions (2026-08-24, supervisor)

- **No VerilogEval 156 run** — not funded. Replaced by a smaller, deliberately *harder*
  circuit set with repeats.
- **Temperature 0.7 only.** The temp-0 arm is dropped; `results/final_temp00/` is superseded.
- **Report deadline Sept 1 2026** — 5 days of experiments, then writing only.

---

## 5-Day Plan

### Day 1 — Pipeline fixes ✅ DONE
Branch `008-control-arm-and-static-evidence`, 4 commits, **88 passed / 3 skipped**.

- [x] **Fix A** — reconcile `_check_fdisplay` with the standardiser's `_is_observed`
      (`8473d33`). Verified against the real corpus: 3 findings → 0, all were false positives.
- [x] **Fix B** — `retry_only` control arm: one extra `gen_driver` sample, zero diagnostics
      (`41ef824`). Separates "the feedback helped" from "a second sample helped".
- [x] **Fix C** — persist `static_findings` + `pyverilog_report` in every result JSON
      (`12cc512`). RQ1/RQ2 evidence was previously discarded.
- [x] **Fix D** — Eval2 scores against valid mutants only (`8d65a8c`).

### Day 2 — Hard-circuit fixtures
- [ ] Write `_prompt.txt` + `_ref.v` for 6 new circuits:
  - CMB: `alu_8bit` (8-bit A/B, 3-bit opcode, zero/carry/overflow flags),
    `barrel_shifter_8bit` (8-bit data, 3-bit amount, direction, arith mode),
    `bcd_to_7seg` (4-bit in, 7-bit out)
  - SEQ: `fsm_sequence_detector` ("1011" overlapping, Moore),
    `fifo_8x8` (`wr_en`/`rd_en`/`full`/`empty`/`data_in`/`data_out`),
    `traffic_light_fsm` (multi-state, timed transitions)
- [ ] Verify each compiles under `iverilog -g2012`
- [ ] One `hybrid` smoke run each (~$1) — catch prompt/parse breakage before the real sweep
- [ ] Expect Pyverilog parse failures on the FSMs; confirm the Verible fallback engages
- [ ] **Drop any circuit that fights us** rather than lose the day

### Day 3 — Error-injection precision/recall (FR-017) — **offline, zero tokens**
- [ ] Injection harness: take passing testbenches, break them in known structural ways
      — swap two port bindings, delete an input driver, truncate a bus width, strip the
      `$monitor`, break the sensitivity list
- [ ] Measure catch rate per taxonomy class → **precision/recall table**
- [ ] Decide `WIDTH_MISMATCH`: implement it or remove it from the taxonomy
      (currently declared but emitted nowhere — the report must not claim a check we lack)
- [ ] Most direct evidence for RQ2, and it works regardless of how the sweep turns out

### Day 4 — Freeze prompts, run the sweep
- [ ] **Freeze all prompts**, tag the commit `prompts-frozen`
- [ ] `python scripts/run_eval.py --modules <12-circuit set> --yes --results-dir results/final_hard_r1`
- [ ] Second repeat → `results/final_hard_r2`
- [ ] 12 circuits × 5 modes × 2 repeats = **120 runs**, ≈1.93M tokens, ≈$15, ~4–6 h
- [ ] Start it in the morning; it is the only long-running step

### Day 5 — Aggregate and produce the tables
- [ ] Per-node failure attribution (already logged — aggregator computes it)
- [ ] Iterations-to-pass distribution
- [ ] Token cost per module per mode
- [ ] Eval0/1/2 across all 5 modes with mean±std from the repeats
      (`scripts/aggregate_repeats.py`)
- [ ] Failure-mode catalogue from the persisted `static_findings`
- [ ] Scenario-level pass rate alongside binary Eval1 (SEQ sits at 70–90% per TB even when
      Eval1 says "fail" — much more informative than the binary)
- [ ] Results tables + figures for the report

### Aug 29 – Sept 1 — Report only
- [ ] Results section: ablation tables, AutoBench comparison, honest caveats
- [ ] Error taxonomy write-up (RQ1) from the Day-3 injection study
- [ ] Per-node failure attribution figures
- [ ] Draft → revision → submission

---

## 🧹 Housekeeping

- [ ] Merge `fix/static-analysis-and-eval-integrity` → `main` (`de0eec1`, `c7f3154`,
      `95b8d3b`, `c0cc1e4`), then `008-control-arm-and-static-evidence` → `main`
- [ ] Add a **402 "out of credits" clean-abort** to `harness.run_sweep`
      (mirror the daily-rate-limit abort)
- [ ] Regenerate `diagrams/*.png` from the updated `.puml`
      (PlantUML not installed locally — use plantuml.com or `brew install plantuml`)

## ❄️ Deferred (out of scope for this deadline)

- VerilogEval 156 held-out run — not funded; note the absence as a limitation in the report
- Temperature sweep / temp-0 controlled arm — dropped
- Cross-model study — deprioritised since 2026-05-20
