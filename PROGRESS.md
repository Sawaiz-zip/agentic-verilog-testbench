# Progress Tracker — S6.ReKI.1

> **For future Claude sessions:** Update this file as work progresses. Read `CLAUDE.md` first for full project context.

**Last updated:** 2026-07-15 (session: real OpenRouter sweeps + pipeline fixes + SEQ prompt)

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
| Phase 4 — Evaluation (Wks 14–16) | 🟢 First real sweeps done | Full 8-fixture × 4-mode ablation run on OpenRouter (Sonnet + gpt-4o-mini) at temp 0.7 AND temp 0. Results below. Remaining: held-out VerilogEval 156 run; Pyverilog precision/recall (FR-017). |
| Phase 5 — Writing (Wks 17–20) | ⚪ Not started | Exposé already done |

**Provider now: OpenRouter (paid).** `.env` → `LLM_STRONG_MODEL=anthropic/claude-sonnet-4.5`, `LLM_CHEAP_MODEL=openai/gpt-4o-mini`, `LLM_TEMPERATURE=0.7` (supervisor default). A temp=0 run is produced separately via inline `LLM_TEMPERATURE=0`.

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

**Reading of the results (honest):**
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

**Pipeline validated end-to-end on OpenRouter; first real ablation results in `results/final_temp07|00/`. Core contribution (Pyverilog static analysis) shows a real, consistent benefit.**

**The one thing that turns "promising on our 8" into a real result: the held-out VerilogEval 156 run.**
1. **Freeze the prompts** (esp. `gen_driver.j2`) — they were tuned on the 8 fixtures, so the 156 must be treated as held-out to test generalisation / overfitting.
2. Run: `python scripts/run_eval.py --modules verilogeval --yes --results-dir results/final_verilogeval156` (624 runs = 156 × 4 modes; ~$40–60; hours). Consider `verilogeval:30` first as a cheaper checkpoint.
3. The `task_id` fix means the 156 no longer collapse in the aggregate — verify `n` per mode ≈ 156.
4. Compare our Eval0/1/2 to AutoBench's published numbers (Eval0 95.7%, Eval2 total 44.8%, CMB 62.2%, SEQ 26.0%) — same HDLBits source, so this is the real head-to-head.

**Other follow-ups:**
- Pyverilog error precision/recall (FR-017) — error-injection experiment (break good TBs in known structural ways, measure catch rate). Most direct proof of the localiser; independent of the 156 run.
- Merge `fix/static-analysis-and-eval-integrity` → `main` (5 commits: `de0eec1`, `c7f3154`, `95b8d3b`, `c0cc1e4`).
- Add a 402 "out of credits" clean-abort to the harness (mirrors the daily-rate-limit abort).

---

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
