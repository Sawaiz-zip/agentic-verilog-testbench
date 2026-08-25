# Progress Tracker — S6.ReKI.1

> **For future Claude sessions:** Update this file as work progresses. Read `CLAUDE.md` first for full project context.

**Last updated:** 2026-08-24 (session: results audit → 4 measurement fixes + `retry_only` control arm)

---

## Phase Status

| Phase | Status | Notes |
|---|---|---|
| Phase 0 — Setup (Wks 1–2) | ✅ Done | All lit review done; env set up; dataset downloaded; Pyverilog smoke test passed |
| Phase 1 — Generation (Wks 3–6) | ✅ Done | CMB pipeline end-to-end; smoke test PASSED (Eval0 5/5, Eval1 4/5, Eval2 4/4) |
| Phase 2 — Pyverilog (Wks 5–9) | ✅ Done | pyverilog_runner + verible fallback + error_reasoner; 17/17 unit tests pass |
| Feature 003 — DUT-gen + temp + results | ✅ Done | gen_dut node (description→DUT); configurable temperature (Constitution v1.1.0); human-readable run summary; offline test suite 36 pass / 1 live-skip |
| Phase 3 — Repair loop (Wks 10–13) | ✅ Done | repair_node + 3-source feedback (static/compile/sim); 4 ablation modes distinct; oscillation + exhaustion termination. |
| Phase 3b — SEQ support | ✅ Done | Deterministic $monitor/clock standardiser (Python-only, idempotent); merge_generation fan-in barrier; SEQ→standardise routing (CMB skips); dff/counter/shift_register fixtures; 60 tests pass. |
| Phase 4 — Evaluation (Wks 14–16) | 🟡 Re-planned after audit | First sweeps (8 fixtures × 4 modes, temp 0.7 + temp 0) were run, then **audited and found unsafe to report** — see § 2026-08-24. Fixed. Now on a 5-day plan: hard circuits → error injection → 120-run sweep. |
| Phase 5 — Writing (Wks 17–20) | ⚪ Not started | Exposé already done |

**Provider: OpenRouter (paid).** `.env` → `LLM_STRONG_MODEL=anthropic/claude-sonnet-4.5`, `LLM_CHEAP_MODEL=openai/gpt-4o-mini`, `LLM_TEMPERATURE=0.7`.

**Scope decisions (2026-08-24, supervisor):**
- **No VerilogEval 156 run** — not funded. A smaller, deliberately *harder* circuit set with repeats replaces it.
- **Temperature 0.7 only.** The temp-0 arm is dropped; `results/final_temp00/` is superseded.

Legend: ✅ done · 🟢 on track · 🟡 partial · 🔴 blocked · ⚪ not started

---

## ✅ Done

### Research & Design
- AutoBench paper (arXiv:2407.03891) read in full and distilled into `CLAUDE.md` § 4
- VerilogEval paper (arXiv:2309.07544) read — benchmark structure understood
- Pyverilog paper read — AST/dataflow/CFG API understood
- Project plan finalized: 5 phases, 20 weeks, ending Sept 1 2026
- Architecture decided: LangGraph + Claude API + Pyverilog + Icarus Verilog
- Pipeline design: 10 nodes wired in LangGraph graph
- 4 research questions formulated; 5 contributions identified
- Exposé (`expose.tex`) written and verified — fits professor's `scrreprt` template
- All 9 references verified correct

### Phase 0 — Setup
- Auto-memory configured: `MEMORY.md`, `user_profile.md`, `project_details.md`
- Full project skeleton (all nodes + prompts) pushed to GitHub
- **Dependencies installed:** langgraph, anthropic, pyverilog 1.3.0, jinja2, pytest, python-dotenv
- **Icarus Verilog 13.0** installed via Homebrew
- **VerilogEval dataset** downloaded → `data/verilog_eval/problems/` (156 problems)
- **Pyverilog smoke test PASSED** on 3 CMB + 1 SEQ module
  - `vast.Ioport` wrapper discovered — handled in `_extract_ports()`
  - Dataflow fails on async reset (`posedge clk or posedge ar`) → catch `FormatError`, AST-only fallback

### Phase 1 — CMB Generation (branch: `phase-1-generation`, merged → `main`)
- classify, extract_spec, gen_scenarios, gen_driver, gen_checker nodes — fully implemented
- icarus.py: `compile_tb` / `simulate_tb` / `eval2` — fully implemented
- mutant_gen.py, evaluate_node, CLI `__main__.py` — fully implemented
- Multi-provider LLM abstraction (Anthropic > Groq/compat > OpenAI)
- 5 CMB fixtures created and verified: alu_1bit, mux2to1, half_adder, comparator_2bit, priority_encoder
- **Smoke test gate PASSED:** Eval0 5/5=100%, Eval1 4/5=80%, Eval2 4/4=100%

### Phase 2 — Pyverilog Static Analysis (branch: `phase-2-pyverilog`)
- `pyverilog_runner.run()` — port-binding mismatch (AST), undriven inputs, unobserved outputs, sensitivity list check, `$fdisplay` presence check
- `verible_runner.run()` — fallback for unparseable LLM-generated Verilog
- `pyverilog_analysis_node` — calls runner + Verible fallback; deterministic, zero LLM calls
- `error_reasoner_node` — calls Sonnet only when report is non-clean; skips LLM (saves tokens) on clean TBs
- **17/17 unit tests pass** (8 pyverilog_runner including 3 SEQ tests, 6 error_taxonomy, 3 config)
- **T107 gate PASSED:** half_adder pipeline → success with Phase 2 active; error_reasoner correctly makes 0 LLM calls on clean TB
- **T108 gate PASSED:** buggy TB with wrong port → 2 PORT_BINDING_MISMATCH errors flagged

---

## 🆕 Day 4–5 (2026-08-25) — Three sweeps, 220 runs, and the answer

Consolidated findings: **`docs/results.md`**. Reproduce with
`python scripts/analyse_results.py --all`.

Prompts frozen at tag `prompts-frozen` before any sweep; none modified afterwards.

| Sweep | Model | Circuits | Runs |
|---|---|---|---|
| `final_hard_r1` | claude-sonnet-4.5 | 12 project | 60 |
| `weak_model_r1` | gpt-4o-mini | same 12 | 60 |
| `verilogeval_weak` | gpt-4o-mini | 20 VerilogEval | 100 |

Zero harness errors across all 220 runs. Total API spend ≈ $9.20.

### The decisive result

**Static analysis fired twice in 314 analyses.** `pyverilog_only` performed **zero repairs
in all three sweeps**. The single VerilogEval finding landed in `compiler_only`, which
ignores static findings by design, so it was never even acted on.

The "model too capable" explanation is **not supported**: `gpt-4o-mini` is far worse at the
task (Eval1 63% → 35% on identical circuits) yet makes essentially the same number of
structural mistakes. Both weak and strong models produce structurally well-formed
testbenches; **87% of failures are semantic** (133 of 153) and need simulation by definition.

The VerilogEval circuits were selected by structural complexity **before** running — 15 of
20 sequential, port counts 6–12, complexity well above the benchmark median. Selecting on
circuit properties rather than observed outcomes is what makes the null result valid: the
sample was biased *toward* the conditions where static faults are possible, and it still
found nothing.

### Statistics, pooled over 220 runs (n=44 per mode)

| mode | Eval1 | 95% CI |
|---|---|---|
| `pyverilog_only` | 20.5% | [11.2, 34.5] |
| `baseline` | 27.3% | [16.3, 41.8] |
| `retry_only` | 29.5% | [18.2, 44.2] |
| `compiler_only` | 34.1% | [21.9, 48.9] |
| `hybrid` | 40.9% | [27.7, 55.6] |

**No pairwise difference reaches p<0.05.** hybrid vs the `retry_only` control: **p=0.372**.

**Variance floor, measured twice independently:** arms taking an identical code path scored
67/67/33% (Sonnet) and 17/50/33% (mini) — a **33-point spread** both times. At temperature
0.7 and this sample size, smaller differences are uninterpretable. This bears directly on
prior work, which reports single-run pass@1 without error bars.

**`retry_only` degrades compilation** on hard circuits: Eval0 70% vs 90–95% elsewhere. A
second attempt without information is worse than no second attempt.

### Corrections made

- **Contribution 5 rescoped.** It claimed per-node attribution of where failures *originate*;
  the data shows 70% `evaluate` / 30% `none`, because that is where failure is *detected*.
  Origin attribution needs per-node ground truth the pipeline does not collect. Reworded
  rather than quietly kept.
- **AutoBench comparison grounded in the paper.** They have no static analysis at all —
  scenario-presence checking, compiler auto-debug, and a `$fdisplay` standardiser, none of
  which parse Verilog. Their ablation reports +8% (auto-debug) and +10% (scenario checking)
  but has **no control arm**, so it cannot separate feedback from retry either. Their
  largest gain (SEQ Eval0 55%→97%) came from the deterministic standardiser — the same
  category as this project's contribution, working then because GPT-4-turbo omitted
  `$fdisplay` and failing now because current models do not.
- **Eval2 is at ceiling** (189/190 mutants caught) and discriminates nothing. Mutants and
  per-mutant outcomes are now persisted so this is auditable in future runs.

### Two premature calls I made and corrected

Recorded because the corrections are part of the method: I reported the completion of
repeat 1 based on a file that `render_report.py` itself creates, and I called the
weak-model hypothesis "confirming itself" on 1 finding in 9 analyses when the final count
was 1 in 79. Both were caught and corrected within the same session.

---

## 🆕 Day 3 (2026-08-24) — Error-injection study: the localiser, measured

Branch: `011-error-injection-study`. Suite: **182 passed, 3 skipped** (was 153).
Raw data: `results/injection_study_final.json`. Write-up:
`specs/011-error-injection-study/NOTES.md`. **Cost: zero tokens.**

First direct measurement of the static localiser, answering RQ2 with numbers instead of
inference from end-to-end pass rates. 14 known-good testbenches, 215 injected faults,
three layers asked the same question: does static analysis flag it, does the compiler
refuse it, does the simulation fail?

**Baseline: 14/14 parsed, 0 false positives → 100% precision on clean input.**

| fault class | n | static | compiler | sim | only static |
|---|---|---|---|---|---|
| `unobserved_output` | 19 | **100%** | 0% | 0% | **100%** |
| `remove_clock_generator` | 6 | **100%** | 0% | 17% | **83%** |
| `width_change` | 22 | **100%** | 0% | 82% | **18%** |
| `undriven_input` | 30 | **100%** | 0% | 97% | 3% |
| `port_drop` | 62 | **100%** | 0% | 98% | 2% |
| `port_rename` | 62 | **100%** | 100% | 0% | 0% |
| `break_edge_sync` *(control)* | 5 | 0% | 0% | 80% | 0% |
| `swap_bindings` *(control)* | 9 | 0% | 0% | 78% | 0% |
| **TOTAL** | **215** | **93%** | **29%** | **56%** | **14%** |

- **Localisation (right class AND right signal): 93%** — exact signal match, not substring.
- **33/215 faults (15%) are missed by the compiler and simulator together; static catches
  30 of those 33 (91%).**

**The headline.** `unobserved_output`: 19 faults, static 100%, compiler 0%, simulator 0%.
A testbench that stops checking an output does not fail — it **passes**, because it is no
longer looking. The simulator cannot see this by construction; the compiler sees legal
Verilog. That is RQ2 demonstrated. `clock_never_toggled` is the second such class: five of
six testbenches with a dead clock still passed their own checks.

**Honest limits.** `port_rename` (62 faults) is caught by the compiler too — we add only
speed. The `swap_bindings` control is invisible to static analysis by design, marking the
boundary of the approach. 14 circuits and 8 self-chosen fault classes is real evidence,
not a benchmark.

### Negative result: `sensitivity_list_error` removed

It caught **0 of 5** injected `break_edge_sync` faults — the exact defect it existed for —
and produced the study's only baseline false positive, on a passing testbench. The cause is
structural: it inspected `always` blocks *inside the testbench*, but LLM testbenches drive
from `initial` blocks and synchronise with `@(posedge clk)`, so it was looking where the
evidence never is. `CLOCK_NEVER_TOGGLED` covers the same concern at 6/6.
`PyverilogReport.sensitivity_errors` → `clock_errors`; the resulting blind spot is recorded
by a test rather than left to be rediscovered. **Six checks remain, all injection-verified.**

### Eight defects found in already-tested code

Three in the harness, which would have **inflated** the numbers: the corpus used the
pipeline's generated DUT instead of the golden one (a malformed generated DUT's compile
error scored as a detection); there was no baseline gate; and `_dut_port_directions`
mis-parsed shared declarations, silently dropping ports.

Five in the analyser, which were **deflating** them and hiding real defects: string
literals and comments were read as code (`$display("PASS: addition_boundary_overflow")`
made the `overflow` output look observed — `unobserved_output` went **47% → 100%** once
fixed); the 009 sensitivity fix was incomplete; the clock-toggle search used a fixed
character window that overran short blocks; "more than one assignment" counted as toggling;
and the clock injector matched one generator style, measuring that class on a sample of
**one** (0% → 100% after the fix).

**The Day-2 figures were therefore produced by a partly broken localiser.** The injection
study is what surfaced that — which is the argument for having run it.

---

## 🆕 Day 2b (2026-08-24) — Both carried gaps closed before Day 3

Branch: `010-width-and-clock-checks`. Full suite: **153 passed, 3 skipped** (was 132/3).
Write-up: `specs/010-width-and-clock-checks/NOTES.md`.

Both checks target defects **the compiler cannot see** — which is the case static analysis
has to make.

- **`WIDTH_MISMATCH` implemented.** It had been declared in the taxonomy since Phase 2 and
  emitted nowhere; the report would have claimed a check that did not exist. It also could
  not have been tested before: every original fixture is 1-bit or uniformly 4-bit. It reads
  both ANSI and Verilog-1995 declaration styles and skips widths it cannot resolve
  (parameters, concatenations, slices) rather than guessing. A width mismatch is silent at
  simulation time — Verilog truncates or zero-extends without a warning — so the testbench
  compiles, runs, and reports wrong results.
- **`CLOCK_NEVER_TOGGLED` added.** Deleting the clock generator from a correct testbench
  previously left the analyser clean: `initial clk = 0;` satisfies `_signal_is_driven`, so
  the undriven-input check cannot see it. The simulation then runs but never advances, and
  every scenario reads back the reset value — the failure looks like a logic error rather
  than a missing clock. The clock is identified from edge expressions in the DUT source,
  not by name convention, and toggle detection is deliberately generous after three false
  positives in this module.
- **Guard added.** `test_every_declared_error_type_is_actually_emitted_somewhere` fails if
  any taxonomy member has no emitting code path, so an unbacked entry cannot reappear.

**Regression: zero findings across all 38 real testbenches** (32 from the July sweep, 6
from the Day-2 smoke runs), and none on four working clock-generator styles.

### Check inventory going into Day 3

| Check | Status |
|---|---|
| `port_binding_mismatch` | ✅ injection-verified |
| `undriven_input` | ✅ injection-verified |
| `unobserved_output` | ✅ injection-verified |
| `missing_fdisplay` (SEQ) | ✅ injection-verified |
| `width_mismatch` | ✅ **now implemented**, verified on 4 circuits |
| `clock_never_toggled` (SEQ) | ✅ **new**, verified on 2 circuits |
| `sensitivity_list_error` | ⚠️ fires only when a testbench never synchronises to an edge — rare. Day 3 quantifies whether it earns its place. |

Six of seven injection-verified. Day 3 turns this spot check into precision/recall figures.

---

## 🆕 Day 2 (2026-08-24) — Six hard fixtures + a second false positive

Branch: `009-hard-circuit-fixtures`. Full suite: **126 passed, 3 skipped** (was 88/3).
Write-up: `specs/009-hard-circuit-fixtures/NOTES.md`.

### Six circuits, chosen for the checks they can exercise

| Fixture | Type | Ports | Exercises |
|---|---|---|---|
| `alu_8bit` | CMB | 7 | port bindings, mixed widths (8/3/1), undriven inputs |
| `barrel_shifter_8bit` | CMB | 5 | mixed widths, mode-dependent behaviour |
| `bcd_to_7seg` | CMB | 2 | differing in/out widths (4 → 7) |
| `fsm_sequence_detector` | SEQ | 5 | multi-state tracking, exposed `state` |
| `fifo_8x8` | SEQ | 9 | port bindings, undriven inputs, registered read |
| `traffic_light_fsm` | SEQ | 4 | timed multi-state, exposed `timer` |

Every golden DUT was validated **behaviourally against its own prompt**, not merely
compiled — a golden that contradicts its description would make every generated testbench
fail Eval1 for a specification reason rather than a quality one, silently corrupting the
ablation. All six parse under Pyverilog; the Verible fallback was not needed.

### Fix E — a second false positive, same family as fix A

`sensitivity_list_error` fired on **all three** correct SEQ testbenches. Two ordinary
correct constructions were being flagged: a clock generator (`always #5 clk = ~clk;`) has
no sensitivity list by design, and a self-checking testbench synchronises with
`@(posedge clk)` from an `initial` block rather than an edge-triggered `always`. Fixed;
a testbench that never synchronises to an edge is still flagged.

### The checks finally fire

| Injected fault | Detected as |
|---|---|
| `alu_8bit`: `.op` → `.opcode` | `port_binding_mismatch` ×2 |
| `alu_8bit`: `.overflow` binding removed | `port_binding_mismatch` |
| `alu_8bit`: `op` never assigned | `undriven_input` |
| `alu_8bit`: `carry` never compared | `unobserved_output` |
| `fifo_8x8`: `.rd_en` → `.read_en` | `port_binding_mismatch` ×2 |
| `fifo_8x8`: `data_in` never assigned | `undriven_input` |
| `fifo_8x8`: `data_out` never checked | `missing_fdisplay` |
| **correct testbench, all six circuits** | **no findings** |

Four of the five checks now have a circuit that can trip them, with no false positives.
Regression on the 32 July testbenches: still 0 findings, 29/32 parses.

### Gaps carried into Day 3

- **`WIDTH_MISMATCH` is still never emitted** — implement it against the new mixed-width
  circuits or remove it from the taxonomy. The report must not claim a check we lack.
- **A clock initialised but never toggled is not caught** — `initial clk = 0;` satisfies
  `_signal_is_driven`, so deleting the clock generator leaves the analyser clean. The
  standardiser repairs this case but the analyser does not report it. A
  `CLOCK_NEVER_TOGGLED` check is cheap; quantify it in the injection study first.

### Fix F — Eval1 verdict decided by a scenario name

The smoke run earned its keep. `fsm_sequence_detector` printed **8 PASS lines and no FAIL
line**, was scored a failure, and burned **all three repair iterations** fixing a
testbench that was already correct — ending `exhausted_iters`. Cause: the Eval1 verdict
searched the whole output for the bare substring `"mismatch"`, and one scenario was named
`immediate_mismatch`. The scenario's *name* was scoring its own run. Unfixed this would
have produced a wrong row for any circuit whose scenario names contain the word, and
burned three repair calls each time.

### Smoke runs (hybrid, one per circuit)

| Circuit | Eval0 | Eval1 | Eval2 | repairs | scenarios |
|---|---|---|---|---|---|
| `alu_8bit` | ✅ | ✅ | 1.00 (5/5 valid) | 1 (sim) | 10/10 |
| `barrel_shifter_8bit` | ✅ | ✅ | 1.00 (5/5 valid) | 1 (sim) | 8/8 |
| `bcd_to_7seg` | ✅ | ✅ | 1.00 (5/5 valid) | 0 | 16/16 |
| `fifo_8x8` | ✅ | ✅ | 1.00 (**3/3 valid of 5**) | 0 | 8/8 |
| `traffic_light_fsm` | ✅ | ✅ | 0.80 (4/5 valid) | 3 (sim) | 7/7 |
| `fsm_sequence_detector` | ✅ | ✗ → **✅ after F** | 1.00 (5/5 valid) | 3 wasted → 1 (sim) | 8/8 → 9/9 |

- **The difficulty level is right.** `alu_8bit` and `barrel_shifter_8bit` failed first-shot
  on exactly the hard cases — arithmetic right shift of a negative value, signed
  comparison — and recovered in one repair; `traffic_light_fsm` needed all three. These
  circuits discriminate between modes, which the original CMB fixtures did not.
- **Fix D is visibly load-bearing.** `fifo_8x8` caught 3 of 3 *valid* mutants, but only 3
  of the 5 generated mutants compiled. Under the old denominator it would have scored 0.60
  instead of 1.00 — a 40-point error on a testbench that missed nothing.

---

## 🆕 Session 2026-08-24 — Results audit, 4 measurement fixes, `retry_only` control arm

Branch: `008-control-arm-and-static-evidence`. Full suite: **88 passed, 3 skipped** (was 73/3).
Full write-up: `specs/008-control-arm-and-static-evidence/NOTES.md`.

### What the audit of the 007 results found

The 8×4 sweeps were re-examined before building on them. Three problems, in order of severity:

1. **The ablation rests on 3 circuits.** All 5 CMB fixtures pass in every mode at both
   temperatures — 40 of 64 runs are constant. Every point of variance comes from `dff`,
   `counter_4bit`, `shift_register`, and the mode ordering flips between temperatures.
   The 100% / 88% / 75% figures in the 2026-07-15 table are not statistically meaningful.
2. **The static layer fired one check, and it was a false positive.** Re-running the
   analyser over all 32 saved testbenches: 3 findings, all `missing_fdisplay`, all wrong.
   Zero findings from the other four checks. `WIDTH_MISMATCH` is in the taxonomy but
   emitted nowhere.
3. **The `pyverilog_only` gain is confounded.** All 5 static-triggered repairs came from
   that false positive. The mechanism was not localisation — a spurious warning caused a
   regeneration that happened to fix an unrelated timing bug. `pyverilog_only` was
   effectively `baseline` + one extra sample, and no control arm separated the two.

### Fixes (4 commits)

| Commit | Fix |
|---|---|
| `8473d33` | **A — `$fdisplay` check reconciled with the standardiser.** The analyser required the output inside a `$display` argument list; the standardiser accepted an `if (q === ...)` self-check. Both now use `_output_is_observed`, de-duplicated against `UNOBSERVED_OUTPUT`. |
| `41ef824` | **B — `retry_only` control arm.** One extra `gen_driver` sample, zero diagnostics. A mode must beat `retry_only`, not just `baseline`, to claim its feedback works. New `regenerate` node; `ALL_MODES` is five. |
| `12cc512` | **C — static-analysis evidence persisted.** New `state.static_findings` (one entry per analysis pass) + final report written to every result JSON. RQ1/RQ2 are computed from this and it was previously discarded. |
| `8d65a8c` | **D — Eval2 valid-mutant denominator.** Non-compiling mutants no longer count against the score (one bad mutant of five had capped it at 0.8). |

### The consequence, stated plainly

**After fix A the static layer reports nothing at all on the 8 original fixtures**, so
`pyverilog_only` collapses onto `baseline` there. The checks are not weak so much as
untestable on 8–17 line circuits with 2–4 unambiguous ports: `port_binding_mismatch` needs
≥3 confusable names, `width_mismatch` needs differing bus widths, `undriven_input` needs
enough inputs to forget one, `sensitivity_list_error` needs `always` blocks the testbench
does not have. This is why the plan below leads with harder circuits and an error-injection
study that measures the localiser directly rather than through end-to-end pass rates.

### Evaluation plan (replaces the VerilogEval 156 plan)

**12 circuits × 5 modes × 2 repeats = 120 runs, temp 0.7 only.** ≈1.93M tokens, ≈$11
(≈$15 with margin), vs ≈$51 for a single-shot 156 run with no error bars.

|  | Easy (existing) | Hard (new) |
|---|---|---|
| **CMB** | `alu_1bit`, `comparator_2bit`, `priority_encoder` | `alu_8bit`, `barrel_shifter_8bit`, `bcd_to_7seg` |
| **SEQ** | `dff`, `counter_4bit`, `shift_register` | `fsm_sequence_detector`, `fifo_8x8`, `traffic_light_fsm` |

`half_adder` and `mux2to1` leave the sweep (constant in every mode) but stay as unit-test
fixtures. Day-by-day schedule in `roadmap.md`.

---

## 🆕 Session 2026-07-15 — First real sweeps, pipeline fixes, SEQ prompt

Branch: `fix/static-analysis-and-eval-integrity`. Full test suite: **73 passed, 3 skipped**.

### Bugs found & fixed (while validating the first paid sweep)
1. **Pyverilog was silently dead (parse bug)** — `commit de0eec1`. LLM testbenches end in `endmodule` with no trailing newline; the runner passed TB+DUT as two files that Pyverilog concatenates, gluing them into `endmodulemodule…` → parse failed on **100%** of testbenches, returning an empty (looks-clean) report. So `pyverilog_only` was silently identical to baseline. Fix: ensure a trailing newline. Parse success **0/8 → 7/8**; Verible covers the last 1/8.
2. **Eval data-integrity (loader + de-dup)** — `commit de0eec1`. `load_module` matched a partial VerilogEval name *before* fixtures, so `mux2to1`/`dff` loaded the wrong circuits; and every VerilogEval task shares `module_name="RefModule"`, which the aggregator de-duped on → all tasks would collapse to one row per mode (would have destroyed the 156 run). Fix: fixtures take precedence; new `task_id` (logical identity) plumbed state→result; aggregate de-dups on `task_id`.
3. **`aggregate_results.py` ignored `--results-dir`** — `commit de0eec1`. Now honored.
4. **Best-so-far retention (Issue A)** — `commit c7f3154`. The repair loop regenerates the whole TB, so a later iteration could be worse than an earlier one, yet the pipeline reported the *last*. This let a mode that repairs more (hybrid) score *below* one that repairs less. Fix: track best-scoring evaluated TB in `best_snapshot`; report it; routing still uses current eval. New `state.best_snapshot`.
5. **SEQ prompt protocol** — `commit c0cc1e4`. SEQ failures were genuine testbench bugs (e.g. `counter_4bit` held reset asserted then expected counting). `gen_driver.j2` now has an explicit sequential protocol (free-running clock; assert-then-DE-ASSERT reset; drive→posedge→settle→check; track state cycle-by-cycle). Validated at temp 0: `counter_4bit` baseline **fail 3/8 → PASS 8/8** (pure generation), `dff` hybrid exhausted-fail → **PASS 30/30** in one repair.

### Infra / tooling
- **Verible installed** (conda-forge Intel build) — the Pyverilog fallback now actually works (this is an Intel Mac; the GitHub release binaries are arm64-only, and the Homebrew formula was removed).
- **LangSmith LLM-call tracing** — `commit 95b8d3b`. `llm_call` now wraps the OpenAI/Anthropic client with `langsmith.wrappers` when `LANGSMITH_TRACING` is on, so each LLM call shows up in the trace (prompt, response, tokens) nested under its node. Project: **S6-ReKI-1**.
- **`scripts/aggregate_repeats.py`** — per-mode mean±std across repeat sweeps (for quantifying temp-0.7 noise).

### First real ablation results (8 fixtures × 4 modes; Sonnet + gpt-4o-mini)

**Temp = 0.7 (`results/final_temp07/`) — realistic:**

| mode | Eval0 | Eval1 | Eval2 | mean repair |
|---|---|---|---|---|
| baseline | 100% | 75% | 72% | 0.00 |
| compiler_only | 100% | 75% | 75% | 0.00 |
| pyverilog_only | 100% | 88% | 85% | 0.25 |
| hybrid | 100% | **100%** | **100%** | 0.50 |

**Temp = 0 (`results/final_temp00/`) — controlled:**

| mode | Eval0 | Eval1 | Eval2 | mean repair |
|---|---|---|---|---|
| baseline | 100% | 62% | 62% | 0.00 |
| compiler_only | 100% | 75% | 75% | 0.00 |
| pyverilog_only | 100% | **88%** | **88%** | 0.25 |
| hybrid | 100% | 75% | 75% | 1.12 |

> ⚠️ **Superseded by the 2026-08-24 audit above.** The `pyverilog_only` and `hybrid` gains
> below are confounded — every static-triggered repair came from a false-positive
> `missing_fdisplay`, and there was no control for the extra LLM sample that repairing
> modes receive. Kept for the record; do not cite these figures.

**Reading of the results (as written on 2026-07-15):**
- ✅ **Eval0 = 100%** everywhere (beats AutoBench's 95.7%).
- ✅ **Static analysis robustly helps** — `pyverilog_only` beats baseline at *both* temperatures (88% vs 75%/62%). Consistent across conditions ⇒ real signal, not noise. This is the core RQ2/RQ3 win.
- ✅ **SEQ prompt fix works** — sequential circuits went from *all-failing* (previous sweeps) to passing in most modes.
- ✅ Hybrid reaches 100% at temp 0.7.
- ⚠️ **Overfitting caveat** — the prompt was tuned *after* seeing these 8 fixtures fail; 100% is optimistic and may not generalise. Needs the held-out 156 run.
- ⚠️ **Residual nondeterminism even at temp 0** (e.g. `counter_4bit` baseline fails but compiler_only passes with 0 repairs). Controlled run is less noisy, not noise-free.
- ⚠️ **Only 8 hand-built fixtures** — top-two mode ordering not yet settled; not comparable to AutoBench until the VerilogEval 156 is run.

**Result folder map (kept clean & separate):**
- `results/final_temp07/` — temp 0.7 sweep (definitive, with all fixes)
- `results/final_temp00/` — temp 0 sweep (definitive, with all fixes)
- `results/sweep_v2|v3`, `results/sweep_temp0`, `results/sweep_seqfix` — earlier exploratory runs (superseded)
- `results/*.json` (root) — legacy single-run debug artifacts

---

## 🔄 Prior features (complete)

Features 003, 004 (repair), 005 (SEQ), 006 (eval harness) complete.

### Feature 006 — Evaluation Harness (spec `006-eval-harness`, branch `006-eval-harness`)
- **Result tagging**: every result JSON now carries `mode` + `module_name`; `wall_clock_ms` fixed to measure the whole run (via `run_started_at` set at graph entry).
- **Aggregator** (`pipeline/eval/aggregate.py`): groups by mode with newest-wins de-dup; per mode → Eval0/1/2 rates, mean repair iters, mean tokens in/out, mean wall time, mean scenarios, final-status distribution, and per-node failure attribution (counts + fractions). Writes `results/summary.json` + a human-readable table. Graceful on empty/malformed.
- **Batch runner** (`pipeline/eval/harness.py`): `run_sweep(modules, modes, limit, opt_in)` with a **token-budget guard** — defaults to the 5 CMB fixtures, refuses > 24 runs without `--yes`, prints a run-count estimate, isolates per-run failures. Module presets: `cmb-fixtures`/`smoke`/`seq-fixtures`/`verilogeval[:N]`.
- **Daily rate-limit abort** (commit `7ae5b55`): `run_sweep` now detects a *daily* token-quota rate limit (e.g. Groq TPD) vs a transient per-minute limit, and aborts the whole sweep immediately with a clear reason instead of failing every remaining (module, mode) pair — still aggregates whatever completed. `llm_call` fast-fails on daily limits (skips pointless retry/backoff); per-minute limits still retry. `run_eval.py` surfaces the abort and exits code 3.
- **CLI**: `scripts/run_eval.py` (estimate → guard → sweep → aggregate); `scripts/aggregate_results.py` now a thin wrapper. Results dir redirectable via `PIPELINE_RESULTS_DIR`.
- **Tests**: `test_aggregate` (all figures on synthetic records, empty, malformed, de-dup, fractions sum to 1), `test_harness_guard` (estimate; refuses over-threshold with zero invocations; proceeds with limit/opt-in; daily-rate-limit abort after first error with zero further invocations), `test_harness_smoke_mocked` (2-mode sweep → mode-tagged results → aggregate). **71 passed, 3 skipped.** Verified live: guard refuses a 624-run sweep with zero token spend.
- **Not done**: the actual paid sweep, and Pyverilog error precision/recall (FR-017, follow-up).
- **Note**: `results/summary.json` currently reflects 8 leftover pre-mode-tagging smoke records grouped under `mode: "unknown"` (not a real ablation result) — will be overwritten once the real sweep runs.

### Feature 005 — SEQ Support (spec `005-seq-support`)
- **Deterministic standardiser** (`pipeline/standardiser/fdisplay_inserter.py`): Python-only, no LLM. Inserts a `$monitor` covering any unobserved DUT outputs and a clock toggle when a declared clock isn't driven; idempotent via a `// [standardised]` marker; fail-safe (returns input unchanged on any error). Satisfies Constitution Principle VI. `standardise_node` now calls it.
- **Graph**: new `merge_generation` no-op fan-in barrier — `gen_driver`+`gen_checker` → `merge_generation` → conditional `route_after_generation` → `standardise` (SEQ) or `pyverilog_analysis` (CMB). `after_repair` re-routes repaired SEQ testbenches through `standardise`. No LangGraph deadlock (verified by test).
- **Fixtures**: `tests/fixtures/seq/{dff,counter_4bit,shift_register}` (_prompt.txt + _ref.v), all compile under iverilog v13.
- **Tests**: `test_fdisplay_inserter.py` (insertion, idempotency, targeting, no-op, fail-safe, no DUT emit) + `test_seq_routing.py` (SEQ→standardise, CMB skips, no deadlock) — offline. One live SEQ test marked `live`. **60 passed, 3 skipped.** CMB + repair paths unaffected (regression green).

### Feature 004 — Repair Loop (spec `004-repair-loop`)
- **repair_node implemented**: regenerates the testbench from structured error feedback via `repair_driver.j2` (Sonnet), logged as node `repair`. Oscillation detection = same error signature recurring OR regenerated testbench identical to previous. Increments `repair_iter`, appends a `repair_history` entry (iteration, feedback_source, tokens).
- **Three feedback sources**: Pyverilog static errors (via `error_reasoner`), compile failures (Eval0), simulation failures (Eval1). `evaluate_node` now writes `error_report` + `feedback_source` on Eval0/Eval1 failure so repair has context; DUT is treated as reference for Eval1 repairs.
- **Four ablation modes now distinct**: BASELINE never repairs; COMPILER_ONLY on compile fails; PYVERILOG_ONLY on static errors; HYBRID on all. Enforced by `should_repair` (post static) + `should_repair_after_eval` (post eval) + `after_repair` (re-analyse vs stop).
- **Graph rewiring**: `repair → after_repair → {pyverilog_analysis, evaluate}`; `evaluate → should_repair_after_eval → {repair, END}`. Confirmed no LangGraph fan-in deadlock on loop re-entry.
- **Termination**: bounded by `max_repair_iter` (3); `final_status` resolves to `oscillated` / `exhausted_iters` / `success` / specific failure.
- **State**: added `repair_history`, `last_repair_signature`, `feedback_source`. Result JSON + `print_run_summary` show the per-iteration repair breakdown.
- **Tests**: `test_repair_node.py` (signature, oscillation, full mode matrix) + `test_repair_loop.py` (success-within-budget, BASELINE no-repair, oscillation→oscillated, exhaustion→exhausted_iters, COMPILER_ONLY compile-repair, no deadlock) — all offline. One live test marked `live`. **49 passed, 2 skipped.**

### Feature 003 — DUT Generation, Configurable Temperature & Human-Readable Results (spec `003-dut-gen-and-results`)
- **DUT generation**: pipeline now runs from a description alone. New `gen_dut` node (Sonnet) between classify and extract_spec synthesises the DUT; classify uses the description only. Graph: `classify → gen_dut → extract_spec → …`. All downstream nodes (extract_spec, gen_driver, pyverilog_analysis, evaluate, mutant_gen) consume `dut_rtl`.
- **Golden DUT eval-only**: `golden_dut` optional; `evaluate_node` uses it only for Eval0/1/2 when present, else the generated DUT; `eval_dut_source` records which.
- **Configurable temperature**: `llm_call(..., temperature=None)` → `LLM_TEMPERATURE` env → 0.7. Hardcoded `temperature=0` removed. Every call logs its temperature. **Constitution Principle IV amended → v1.1.0.** error_reasoner JSON parse hardened with fallback.
- **Human-readable results**: result JSON now has `nl_description`, `dut_rtl`, `eval_dut_source`, `scenario_results`, `scenarios_passed/total`, `tokens_in/out_total`. New `pipeline/reporting.py` (`parse_scenarios`, `print_run_summary`) prints a summary each run.
- **Tests**: `tests/conftest.py` `fake_llm`/`fake_llm_factory`/`mock_icarus` fixtures → whole suite offline (zero tokens). Full-flow mocked integration test covers CMB/SEQ, golden-vs-generated eval DUT, malformed-output robustness, should_repair routing. Live test marked `live`, auto-skips without a key. **36 passed, 1 skipped.**

---

## ⏭️ Next Session — Start Here

**Day 1 of the 5-day plan is done** (branch `008-control-arm-and-static-evidence`, 4 commits,
88 tests green). Remaining schedule — full detail in `roadmap.md`:

- **Day 2** — build the 6 hard fixtures (`alu_8bit`, `barrel_shifter_8bit`, `bcd_to_7seg`,
  `fsm_sequence_detector`, `fifo_8x8`, `traffic_light_fsm`); verify each compiles under
  `iverilog`; one hybrid smoke run each (~$1) to catch breakage early. Drop any circuit that
  fights us rather than lose the day.
- **Day 3** — **error-injection precision/recall (FR-017)**. Break passing testbenches in each
  taxonomy class (swap two port bindings, delete an input driver, truncate a bus width, strip
  the `$monitor`, break the sensitivity list) and measure the catch rate per class. Offline,
  zero tokens, and the most direct evidence for RQ2 — a check that cannot catch a deliberately
  injected fault will not be rescued by more LLM runs.
- **Day 4** — **freeze all prompts** (tag `prompts-frozen`), then run
  12 circuits × 5 modes × 2 repeats = 120 runs at temp 0.7 (≈$15, ~4–6 h).
- **Day 5** — aggregate: per-node failure attribution, iterations-to-pass, token cost per
  module per mode, Eval0/1/2 across all 5 modes with error bars, failure-mode catalogue from
  the persisted `static_findings`, tables + figures.
- **Aug 29 – Sep 1** — report only. No new experiments.

## 🚧 Blocked / Waiting

- Nothing — all blockers resolved by supervisor email (2026-05-26)

---

## Notes / Decisions Log

*Append here as decisions are made in future sessions. Format: `YYYY-MM-DD — decision — rationale`.*

- **2026-05-10** — Adopted LangGraph over hand-rolled script — explicit graph + observability for the per-node failure analysis we want as a contribution
- **2026-05-10** — Chose Claude API over GPT-4 — better instruction following + cheaper Haiku tier for classification nodes
- **2026-05-10** — Decided to replace AutoBench's LLM-based `$fdisplay` standardizer with deterministic Python parser — fragile LLM behaviour on a mechanical task; key SEQ contribution
- **2026-05-10** — CMB before SEQ — paper achieved only 26% on SEQ; we de-risk by getting CMB solid first
- **2026-05-20** — **Scope pivot:** project realigned from "RTL error localisation" to "testbench generation + Pyverilog-based early error localisation" to match the official S6.ReKI.1 description from Prof. Wen. Pyverilog localisation stays as the differentiator vs AutoBench; testbench is the artefact being generated.
- **2026-05-20** — Supervisor priority confirmed: **pipeline architecture > raw benchmark accuracy**. Free-tier Claude API is sufficient. Cross-model study deprioritised; cost/budget items dropped from the supervisor email.
- **2026-05-20** — VerilogEval adopted as the default benchmark (public, ships golden RTL + testbenches) so we are not blocked on a supervisor-provided dataset.
- **2026-05-20** — Added Verible as a fallback static-analysis backend in case Pyverilog rejects LLM-generated code; smoke test moved to Phase 0.
- **2026-05-20** — Repair loop gets oscillation detection (break if same error report repeats) and Eval2 (mutant-pass) added to the metrics.
- **2026-05-20** — Writing schedule moved earlier: report skeleton in week 6, complete first draft by end of week 16, Phase 5 is revision only.
- **2026-06-24** — Phase 1 implementation complete and smoke-tested. classify, extract_spec, gen_scenarios, gen_driver, gen_checker nodes implemented; icarus.py (compile_tb/simulate_tb/eval2) working; mutant_gen.py, evaluate_node, CLI __main__.py all implemented; 5 CMB fixtures created (alu_1bit, mux2to1, half_adder, comparator_2bit, priority_encoder), all compile with iverilog; graph builds with all 10 nodes. Smoke set results: Eval0 5/5=100%, Eval1 4/5=80% (priority_encoder fails — LLM hallucinated expected pos==2 for in=8 but correct is pos==3; repair loop will address), Eval2 4/4=100% on passing modules. Phase 1 gate PASSED.
- **2026-06-24** — Switched from Anthropic API to Groq free tier (Llama-3.3-70b-versatile via OpenAI-compat endpoint). Added multi-provider LLM abstraction in llm.py: Anthropic > compat (LLM_API_KEY+LLM_BASE_URL) > OpenAI. Haiku/Sonnet names map to cheap/strong Groq models via env vars LLM_CHEAP_MODEL and LLM_STRONG_MODEL.
- **2026-06-24** — Phase 2 complete: pyverilog_runner.run() implements port-binding mismatch detection (AST), undriven-input + unobserved-output heuristics (comparison/if/display pattern matching), sensitivity-list check for SEQ circuits, $fdisplay presence check for SEQ. Verible fallback added. error_reasoner_node skips LLM when report is clean (saves tokens). 17/17 unit tests pass. T107 gate: half_adder pipeline still success with Phase 2 active; error_reasoner correctly makes zero LLM calls on clean TB.
- **2026-06-24** — Fixed two gen_driver/gen_scenarios prompt bugs discovered during smoke test: (1) LLM generating "invalid" inputs (a=2 on 1-bit signal) expecting 'bx outputs — added STRICT RULES to gen_scenarios.j2 and requirements to gen_driver.j2 prohibiting out-of-range values; (2) simulate_tb matched "FAIL" too broadly (caught "failed" in debug prints) — tightened regex to r'\bFAIL\s*:' to only catch deliberate PASS/FAIL markers.
- **2026-05-26** — Supervisor email reply received from Shengchao (cc: Jiajun Wu, Wen Bing). All open questions resolved:
  - ✅ Pyverilog static analysis approach confirmed as correct
  - ✅ VerilogEval confirmed as sufficient dataset
  - ✅ Golden models from VerilogEval confirmed for evaluation
  - ✅ Follow AutoBench metrics (Eval0/1/2)
  - ✅ Meeting cadence: monthly; no May meeting; June slot via poll
  - ✅ Progress sharing: Google Doc + GitHub repo (supervisors will leave comments)
  - ✅ Office hours: Wednesday 17:00–18:00 for ad-hoc questions
  - ✅ Phase 1 implementation can begin immediately — no blockers remain
- **2026-07-15** — Switched provider to **OpenRouter** (paid): strong=`claude-sonnet-4.5`, cheap=`gpt-4o-mini`. Groq free tier kept hitting daily limits. Provider abstraction unchanged (OpenAI-compat).
- **2026-07-15** — Fixed the **Pyverilog parse bug** (missing newline glued TB+DUT) — the static-analysis layer had been silently inert (0/8 parse). Now 7/8, Verible covers the rest. This unblocked the whole RQ2/RQ3 contribution.
- **2026-07-15** — Added **`task_id`** as the logical circuit identity (distinct from Verilog `module_name`, which is `RefModule` for all VerilogEval tasks). Aggregate de-dups on it. Prevents the 156-run from collapsing to n=1/mode.
- **2026-07-15** — Added **best-so-far retention** to the repair loop (report the best evaluated TB, not the last) — "more repair" can no longer produce a worse reported result.
- **2026-07-15** — Added a **strict SEQ protocol** to `gen_driver.j2` (reset de-assertion, clock/edge/settle/check timing). SEQ went from all-failing to passing in most modes. NOTE: tuned on the 8 fixtures ⇒ treat the 156 as held-out.
- **2026-07-15** — Wrapped LLM clients with **LangSmith tracing** so each call (prompt/response/tokens) shows under its node in project S6-ReKI-1.
- **2026-07-15** — First real ablation results (8 fixtures): **static analysis robustly beats baseline** (pyverilog_only 88% vs baseline 75%/62% at both temps); hybrid 100% at temp 0.7. Caveats: 8 fixtures only, prompt tuned on them, residual temp-0 nondeterminism → next step is the held-out VerilogEval 156.
