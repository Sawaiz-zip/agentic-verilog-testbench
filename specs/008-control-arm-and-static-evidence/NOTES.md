# 008 — Control Arm, Static-Analysis Evidence & Measurement Fixes

**Date:** 2026-08-24 · **Branch:** `008-control-arm-and-static-evidence`

Cross-cutting session (touches features 002/004/006), recorded here rather than
editing the frozen per-feature specs — same convention as `007`. Living status is in
`docs/research-log.md`; the day-by-day plan is in `docs/roadmap.md`.

## Context

Supervisor decision: **do not run the full VerilogEval 156** (no funding for it). Instead
run a smaller, deliberately *harder* circuit set with repeats, at **temperature 0.7 only**
(the temp-0 arm is dropped). Auditing the 007 results before committing to that plan
surfaced four defects that made the recorded numbers unsafe to report.

## Findings from the audit of `results/final_temp07` / `final_temp00`

1. **The ablation rests on 3 circuits.** All 5 CMB fixtures pass in every mode at both
   temperatures — 40 of the 64 runs are constant. Every point of variance comes from
   `dff`, `counter_4bit`, `shift_register`. Mode ordering flips between temperatures.
2. **The static layer fired one check, and it was wrong.** Re-running the analyser over
   all 32 saved testbenches produced 3 findings, all `missing_fdisplay`, all false
   positives (see fix A). Zero `port_binding_mismatch`, `undriven_input`,
   `unobserved_output` or `sensitivity_list_error`. `WIDTH_MISMATCH` is declared in the
   taxonomy but emitted nowhere in the codebase.
3. **The reported `pyverilog_only` gain is confounded.** Every static-triggered repair in
   both sweeps (5/5) came from that false positive. The mechanism was not localisation —
   it was a spurious warning causing a regeneration that happened to fix an unrelated
   sequential-timing bug. `pyverilog_only` was, in effect, `baseline` + one extra sample.

## Changes

| Commit | Change | Why |
|---|---|---|
| `8473d33` | **Fix A — reconcile the `$fdisplay` check with the standardiser** | `_check_fdisplay` required the output inside a `$display` argument list; the standardiser's `_is_observed` accepted an `if (q === ...)` self-check. Self-checking SEQ testbenches were flagged by one component and ignored by the other. Both now use `_output_is_observed`; SEQ outputs are de-duplicated against `UNOBSERVED_OUTPUT` so the taxonomy does not double-count. |
| `41ef824` | **Fix B — `retry_only` control arm** | Every repairing mode gets a second LLM generation that baseline does not. Nothing separated "the feedback helped" from "a second sample helped". `retry_only` resamples `gen_driver` once with zero diagnostics. A mode must now beat `retry_only`, not just `baseline`. New `regenerate` node; `ALL_MODES` is five. |
| `12cc512` | **Fix C — persist static-analysis evidence** | `pyverilog_report` is overwritten on every repair re-analysis, so evidence for all but the final pass was unrecoverable. New `state.static_findings` (reducer-appended, one entry per pass) plus the final report are written to every result JSON. RQ1 and RQ2 are computed from exactly this. |
| `8d65a8c` | **Fix D — Eval2 valid-mutant denominator** | Non-compiling mutants were skipped in the numerator but counted in the denominator, capping the score at 0.8 for one bad mutant out of five — indistinguishable in the table from a genuinely imperfect testbench. `eval2_detailed()` returns `(rate, caught, valid, total)`; validity counts are persisted. |

## Consequence to carry into the report

**After fix A the static layer reports nothing at all on the 8 original fixtures.** On that
circuit set `pyverilog_only` now collapses onto `baseline`. This is the honest state: the
checks are not weak so much as untestable there. Four of the five cannot fire on 8–17 line
circuits with 2–4 unambiguous ports:

- `port_binding_mismatch` needs ≥3 confusable port names.
- `width_mismatch` needs buses of differing widths (every fixture is 1-bit or uniformly 4-bit).
- `undriven_input` needs enough inputs for the model to forget one.
- `sensitivity_list_error` needs `always` blocks in the testbench; none of ours have any.

This motivates the hard-circuit set below and the error-injection study, which measures the
localiser directly instead of through end-to-end pass rates.

## Validation

- Full suite: **88 passed, 3 skipped** (was 73/3). 15 new tests.
- Fix A verified against the real corpus: re-running the analyser over the 32 saved
  testbenches goes from 3 findings (all spurious) to 0. Genuinely unobserved outputs are
  still flagged, and reported once rather than twice (unit tests).
- All five ablation graphs compile; `retry_only` never reaches the repair node (unit test).

## Evaluation plan (supersedes the VerilogEval 156 plan in 007)

**12 circuits × 5 modes × 2 repeats = 120 runs, temperature 0.7 only.**
≈1.93M tokens, ≈$11 (≈$15 with margin) — against ≈$51 for a single-shot 156 run with no
error bars.

|  | Easy (existing) | Hard (new) |
|---|---|---|
| **CMB** | `alu_1bit`, `comparator_2bit`, `priority_encoder` | `alu_8bit`, `barrel_shifter_8bit`, `bcd_to_7seg` |
| **SEQ** | `dff`, `counter_4bit`, `shift_register` | `fsm_sequence_detector`, `fifo_8x8`, `traffic_light_fsm` |

6 CMB / 6 SEQ and 6 easy / 6 hard, giving both splits in the results table. `half_adder`
and `mux2to1` are dropped from the sweep (constant in every mode, zero information) but
kept as unit-test fixtures — the T107 gate uses `half_adder`.

## Follow-ups

- Hard-circuit fixtures + smoke run (Day 2).
- Error-injection precision/recall — FR-017 (Day 3). Offline, zero tokens.
- Freeze prompts, then the 120-run sweep (Day 4).
- Aggregate: per-node attribution, iterations-to-pass, token cost, failure modes (Day 5).
