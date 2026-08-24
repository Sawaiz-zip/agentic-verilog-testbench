---
description: "Task list — Evaluation harness (ablation study)"
---

# Tasks: Evaluation Harness

**Feature dir**: `specs/006-eval-harness`
**Input**: [spec.md](./spec.md) · [plan.md](./plan.md) · [data-model.md](./data-model.md) · [contracts/interfaces.md](./contracts/interfaces.md)
**Working branch**: `phase-2-pyverilog`

Legend: `[P]` = parallelizable · `[USn]` = maps to spec user story.

---

## Phase 1: Foundational — tag results with mode + module (blocks aggregation)

- [x] T001 Edit `pipeline/state.py`: add `mode: str` field.
- [x] T002 Edit `pipeline/nodes/evaluate.py` `_write_result`: add `"mode": state.get("mode", "")`
  to the result dict (`module_name` already present).
- [x] T003 Edit `pipeline/__main__.py`: set `initial_state["mode"] = mode.value`.

**Checkpoint**: a single `python -m pipeline run ...` writes a result JSON containing `mode`.

---

## Phase 2: User Story 1 + 2 — Aggregator (P1) 🎯 MVP

**Goal**: group results by mode; compute the comparison + failure attribution.
**Independent test**: synthetic records → every figure matches hand-computed values.

- [x] T004 [US1] Create `pipeline/eval/aggregate.py` `aggregate(results_dir="results")`:
  read `results/*.json` (skip `summary.json` + malformed via try/except); de-dup newest per
  `(module_name, mode)` by file mtime; group by `mode`; per mode compute `n`, `eval0/1/2_pass_rate`,
  `mean_repair_iter`, `mean_tokens_in`/`mean_tokens_out` (prefer `tokens_in_total`/`tokens_out_total`,
  else sum `llm_calls`), `mean_wall_clock_ms`, `mean_scenarios_passed`/`mean_scenarios_total`;
  write `results/summary.json`; return the dict. Graceful on empty (return `{}`).
- [x] T005 [US2] Add to `pipeline/eval/aggregate.py`: per-mode `final_statuses` distribution and
  `failure_stages` attribution as `{stage_or_"none": {"count", "fraction"}}` (fractions per mode
  sum to 1.0). Records with no `mode` group under `"unknown"`.
- [x] T006 [US1] Add `print_summary_table(summary)` to `pipeline/eval/aggregate.py`: human-readable
  per-mode table (rates, mean repair/tokens/time, top final statuses + failure stages).

**Checkpoint**: `test_aggregate.py` (T012) passes.

---

## Phase 3: User Story 3 — Budget-aware batch runner (P1)

**Goal**: run modules × modes with a token-budget guardrail.
**Independent test**: estimate correct; over-threshold without opt-in performs zero runs.

- [x] T007 [US3] Create `pipeline/eval/harness.py`: `SAFE_THRESHOLD = 24`;
  `DEFAULT_MODULES = ["alu_1bit","mux2to1","half_adder","comparator_2bit","priority_encoder"]`;
  `estimate_runs(modules, modes, limit=None)`; `resolve_modules(selector)` handling keywords
  `cmb-fixtures`/`smoke` → DEFAULT_MODULES, `seq-fixtures` → SEQ fixture names,
  `verilogeval[:N]` → first N problem keys, else explicit names (reuse `__main__.load_module`).
- [x] T008 [US3] Add `run_sweep(modules, modes, *, limit=None, opt_in=False, results_dir="results",
  graph_invoke=None)` to `pipeline/eval/harness.py`: print the run-count estimate; if effective
  `n > SAFE_THRESHOLD` and not `opt_in` → refuse (return `{"ran":0,"refused":True,"n":n}`), zero
  invocations; else for each (module, mode): build the mode-tagged initial state
  (`state["mode"]=mode.value`, `run_started_at`), invoke the graph (via injectable `graph_invoke`,
  default real `build_graph`+`invoke`), rely on `evaluate_node` to write the result; wrap each run
  in try/except recording `final_status="harness_error"` and continuing. Return
  `{"ran","refused","n","results"}`.

**Checkpoint**: `test_harness_guard.py` (T013) passes; a refused sweep calls `graph_invoke` zero times.

---

## Phase 4: CLI

- [x] T009 Create `scripts/run_eval.py`: argparse CLI `--modules` (default `cmb-fixtures`),
  `--modes` (default all 4), `--limit N`, `--yes` (opt_in), `--results-dir`, `--no-aggregate`.
  Resolve modules/modes, call `run_sweep`, then (unless `--no-aggregate`) `aggregate` +
  `print_summary_table`.
- [x] T010 Rewrite `scripts/aggregate_results.py` as a thin wrapper calling
  `pipeline.eval.aggregate.aggregate()` + `print_summary_table` (back-compat).

---

## Phase 5: Tests (offline)

- [x] T011 [P] Ensure `pipeline/eval/__init__.py` exports nothing breaking; confirm imports.
- [x] T012 [P] [US1] Create `tests/unit/test_aggregate.py`: write synthetic result dicts (2 modes,
  known eval flags/tokens/repair/statuses/failure_stages) to a tmp dir; assert every computed rate,
  mean, and distribution; empty dir → `{}`; a malformed file is skipped; newest-wins de-dup on a
  duplicate `(module,mode)`; per-mode failure fractions sum to 1.0.
- [x] T013 [P] [US3] Create `tests/unit/test_harness_guard.py`: `estimate_runs` arithmetic;
  `run_sweep` over-threshold + `opt_in=False` returns `refused=True`, `ran=0`, and the injected
  `graph_invoke` (a spy) is never called; with `opt_in=True` or a bounding `limit` it runs and the
  spy is called `n` times. No API calls.
- [x] T014 [US1] Create `tests/integration/test_harness_smoke_mocked.py`: `run_sweep` over 1 CMB
  fixture × 2 modes with `fake_llm` + `mock_icarus` into a tmp results dir; assert 2 result files,
  each tagged with its `mode`; `aggregate(tmp)` returns 2 mode entries.

**Checkpoint**: `pytest -q` green offline; no API calls.

---

## Phase 6: Polish

- [x] T015 Run full `pytest -q` offline; fix failures; confirm prior features still pass.
- [x] T016 Update `docs/research-log.md`: mark the evaluation harness done; note the budget guard, the
  summary schema, and how to run a sweep. Mention precision/recall (FR-017) as a follow-up.

---

## Dependencies & Execution Order

- **Phase 1 (T001–T003)** first — tagging unblocks meaningful aggregation.
- **Phase 2 (aggregator)** next — MVP; the headline numbers.
- **Phase 3 (runner)** depends on nothing in Phase 2 (can proceed in parallel) but shares the
  result schema.
- **CLI (T009–T010)** after harness + aggregate exist.
- **Tests (T011–T014)** after their targets exist.
- **Polish (T015–T016)** last.

### Same-file cautions (NOT parallel)

- `pipeline/nodes/evaluate.py`: T002 only.
- `pipeline/eval/aggregate.py`: T004, T005, T006 — in order.
- `pipeline/eval/harness.py`: T007, T008 — in order.

### Parallel opportunities

- T012 ∥ T013 (different test files) once their targets exist.
- Phase 2 (aggregator) ∥ Phase 3 (harness) — different files.

---

## Implementation Strategy

**MVP = Phase 1 + Phase 2**: tag results and produce the per-mode comparison + failure attribution
from whatever result records already exist. Then add the budget-aware runner (US3), the CLI, tests,
and polish.

**Token discipline**: all tasks are offline. Aggregation runs on synthetic/existing records; the
runner is tested with an injected mock invoke and `fake_llm`. The only token-spending path is an
explicit real sweep via `scripts/run_eval.py` (guarded, opt-in for anything large).
