# TODO — S6.ReKI.1

Living task list. Full context in `CLAUDE.md`; status/results in `PROGRESS.md`.
Last updated: 2026-07-15.

## 🔜 Next (highest value)

- [ ] **Held-out VerilogEval 156 run** — the real head-to-head vs AutoBench.
  - [ ] Freeze prompts first (esp. `gen_driver.j2`) — they were tuned on the 8 fixtures.
  - [ ] `python scripts/run_eval.py --modules verilogeval --yes --results-dir results/final_verilogeval156` (624 runs; ~$40–60; hours). Consider `verilogeval:30` as a cheaper checkpoint first.
  - [ ] Verify aggregate shows n≈156 per mode (task_id fix prevents collapse).
  - [ ] Compare our Eval0/1/2 to AutoBench (Eval0 95.7%, Eval2 total 44.8% / CMB 62.2% / SEQ 26.0%).

- [ ] **Pyverilog error precision/recall (FR-017)** — error-injection experiment: take good
      testbenches, break them in known structural ways (wrong port, missing `$monitor`, undriven
      input), measure how many Pyverilog catches. Most direct proof of the localiser; independent
      of the 156 run.

## 🧹 Housekeeping

- [ ] Merge `fix/static-analysis-and-eval-integrity` → `main` (commits `de0eec1`, `c7f3154`, `95b8d3b`, `c0cc1e4`).
- [ ] Add a **402 "out of credits" clean-abort** to `harness.run_sweep` (mirror the daily-rate-limit abort).
- [ ] Regenerate `diagrams/*.png` from the updated `.puml` (PlantUML not installed locally — use plantuml.com or `brew install plantuml`).
- [ ] Report **scenario-level pass rate** alongside binary Eval1 (SEQ is 70–90% per TB even when Eval1 marks it failed).
- [ ] Optional: 3× repeat sweeps at temp 0.7 for mean±std error bars (`scripts/aggregate_repeats.py`).

## ✅ Done this session (2026-07-15)

- [x] Switch provider to OpenRouter (Sonnet + gpt-4o-mini).
- [x] Fix Pyverilog parse bug (static analysis was 0/8 → 7/8).
- [x] Add `task_id` (prevents 156-run aggregation collapse) + loader precedence fix.
- [x] Best-so-far repair retention (Issue A).
- [x] LangSmith LLM-call tracing.
- [x] Strict SEQ protocol in `gen_driver.j2` (counter/dff flipped to PASS).
- [x] Install Verible (conda-forge) — fallback parser now works.
- [x] First real ablation sweeps at temp 0.7 and temp 0 (`results/final_temp07|00/`).
- [x] Update PROGRESS.md, README.md, diagrams, spec notes.

## 📅 Later (Phase 5 — writing, deadline Sept 1 2026)

- [ ] Results section (ablation tables + AutoBench comparison + honest caveats).
- [ ] Error taxonomy write-up (RQ1) from the injection experiment.
- [ ] Per-node failure attribution figures (already logged per run).
- [ ] Final report draft → revision → submission.
