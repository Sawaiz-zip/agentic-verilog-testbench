---
description: "Task list — Phase 3 repair loop (static + compiler + simulation feedback)"
---

# Tasks: Repair Loop

**Feature dir**: `specs/004-repair-loop`
**Input**: [spec.md](./spec.md) · [plan.md](./plan.md) · [data-model.md](./data-model.md) · [contracts/interfaces.md](./contracts/interfaces.md)
**Working branch**: `phase-2-pyverilog`

Legend: `[P]` = parallelizable · `[USn]` = maps to spec user story.

---

## Phase 1: Foundational — state schema (blocks everything)

- [x] T001 Edit `pipeline/state.py`: add `repair_history: Annotated[list[dict], operator.add]`, `last_repair_signature: str`, `feedback_source: Literal["static","compile","simulation",""]`.

**Checkpoint**: `python -c "import pipeline.state"` clean.

---

## Phase 2: User Story 1 — Automatically repair a broken testbench (P1) 🎯 MVP

**Goal**: `repair_node` regenerates the testbench from error feedback and the loop re-checks.
**Independent test**: unit test — repair_node returns a new `driver_rtl`, increments `repair_iter`, logs one `repair_history` entry.

- [x] T002 [US1] Implement `_error_signature(error_report)` in `pipeline/nodes/repair.py` — stable string from sorted `(error_type, signal or first detail key)`.
- [x] T003 [US1] Implement `repair_node` in `pipeline/nodes/repair.py`: render `repair_driver.j2` with `driver_rtl`, `error_report`, `spec`, `scenarios`, `module_name`; `llm_call(node="repair", model=cfg.model_strong)`; `extract_code_block(...,"verilog")` with raw-text fallback; compute signature; oscillation if signature == `last_repair_signature` OR regenerated driver == current `driver_rtl` → set `oscillation_detected=True` and do NOT increment; else `repair_iter+1`, append `repair_history` entry `{iteration, feedback_source, tokens_in, tokens_out, error_signature}`; snapshot `last_error_report`, set `last_repair_signature`; return `driver_rtl`, `llm_calls`.
- [x] T004 [US1] Review/adjust `prompts/repair_driver.j2`: ensure it surfaces `error_type`, compile `detail`, and `failing_scenarios` so compile/sim feedback is actionable.

**Checkpoint**: `repair_node` unit test (T014) passes.

---

## Phase 3: User Story 3 — Loop always terminates cleanly (P1)

*(Sequenced before US2 because termination routing is needed for the mode tests.)*

**Goal**: routing + finalisation guarantee bounded, precise termination.
**Independent test**: scripted oscillation → `oscillated`; persistent distinct errors → `exhausted_iters`; `repair_iter <= max` always.

- [x] T005 [US3] Add `after_repair(state)` in `pipeline/nodes/repair.py`: return `"evaluate"` if `oscillation_detected` or `repair_iter > max_repair_iter`, else `"gen_driver"`.
- [x] T006 [US3] Edit `pipeline/nodes/evaluate.py` finalisation: resolve `final_status` in order — `oscillation_detected`→`oscillated`; evals pass→`success`; `repair_iter >= max` and not passed→`exhausted_iters`; else specific `failed_compile`/`failed_eval1`/`failed_eval2`.
- [x] T007 [US3] Edit `pipeline/graph.py`: replace fixed `repair→gen_driver` with conditional `after_repair` → `{gen_driver, evaluate}`.

**Checkpoint**: oscillation + exhaustion integration tests (T015) pass; loop never exceeds max.

---

## Phase 4: User Story 2 — Distinct behaviour per ablation mode (P1)

**Goal**: BASELINE/COMPILER_ONLY/PYVERILOG_ONLY/HYBRID trigger repair per their definitions.
**Independent test**: same faulty module under each mode → repair counts match the mode matrix.

- [x] T008 [US2] Refine `should_repair(state, mode)` in `pipeline/nodes/repair.py` (post static analysis): BASELINE/COMPILER_ONLY → `"evaluate"`; empty `error_report` → `"evaluate"`; `repair_iter>=max` or `oscillation_detected` → `"evaluate"`; PYVERILOG_ONLY/HYBRID with non-empty error_report → `"repair"`.
- [x] T009 [US2] Add `should_repair_after_eval(state, mode)` in `pipeline/nodes/repair.py` (post evaluate): BASELINE/PYVERILOG_ONLY → `"END"`; `eval0 and eval1` → `"END"`; `repair_iter>=max` or `oscillation_detected` → `"END"`; COMPILER_ONLY → `"repair"` iff not eval0 else `"END"`; HYBRID → `"repair"` iff not eval0 or not eval1 else `"END"`.
- [x] T010 [US2] Edit `pipeline/nodes/evaluate.py`: on Eval0 fail set `error_report=[compile_error{detail}]`, `feedback_source="compile"`; on Eval1 fail set `error_report=[eval1_mismatch{failing_scenarios, detail}]`, `feedback_source="simulation"`; clear `error_report` on success. Keep Eval2/mutants only after Eval0+Eval1 pass and reuse cached mutants.
- [x] T011 [US2] Edit `pipeline/graph.py`: add conditional `evaluate → should_repair_after_eval → {repair, END}` (replaces fixed `evaluate→END`); import `END`.

**Checkpoint**: all-four-modes integration test (T016) passes.

---

## Phase 5: User Story 4 — Auditable repair history (P2)

**Goal**: persist per-iteration history in the result.

- [x] T012 [US4] Edit `pipeline/nodes/evaluate.py` `_write_result`: add `repair_history`, `feedback_source` (repair_iter already persisted) to the result JSON.
- [x] T013 [US4] Edit `pipeline/reporting.py` `print_run_summary`: if `repair_history` non-empty, print a one-line-per-iteration breakdown (iteration, source, tokens).

**Checkpoint**: a repaired run's result lists each iteration with source + tokens.

---

## Phase 6: Tests (offline by default; one live)

- [x] T014 [P] [US1] Extend `tests/conftest.py`: add `"repair"` canned response; add a `fake_llm_scripted` fixture with a per-node response queue (stateful counter) so tests can return still-broken vs fixed TB across calls; every log carries `temperature`.
- [x] T015 [P] [US1] Create `tests/unit/test_repair_node.py`: `_error_signature` stability; `repair_node` increments + logs history; oscillation on identical signature; oscillation on identical regenerated driver.
- [x] T016 [US3] Create `tests/integration/test_repair_loop.py` (part A): scripted oscillation → `final_status=="oscillated"`; persistent distinct errors → `exhausted_iters`; scripted fix on 2nd try → `success`; assert `repair_iter <= max_repair_iter` in all; assert a full repair cycle completes (no LangGraph fan-in deadlock).
- [x] T017 [US2] Create `tests/integration/test_repair_loop.py` (part B): same faulty module under all 4 modes → assert repair counts / `repair_history` length match the mode matrix (BASELINE 0; PYVERILOG_ONLY on static; COMPILER_ONLY on compile; HYBRID on any).
- [x] T018 [P] Create `tests/integration/test_repair_live.py`: `@pytest.mark.live`, skip without key; one real run that reports `repair_iter` and a populated `repair_history` (do not assert success — model-dependent).

**Checkpoint**: `pytest -q` green offline; `pytest -m live` skipped without key.

---

## Phase 7: Polish

- [x] T019 Run full `pytest -q` offline; fix failures; confirm feature-003 tests still pass.
- [x] T020 Update `docs/research-log.md`: mark Phase 3 repair loop done; note the 4-mode matrix, oscillation/exhaustion, repair_history.

---

## Dependencies & Execution Order

- **T001** first (schema).
- **US1 (T002–T004)** MVP: the repair mechanism.
- **US3 (T005–T007)** termination routing — needed before mode tests can run loops safely.
- **US2 (T008–T011)** mode semantics + eval feedback + graph wiring.
- **US4 (T012–T013)** logging/reporting.
- **Tests (T014–T018)** after their targets exist; T014 (conftest) before T015–T017.
- **Polish (T019–T020)** last.

### Same-file cautions (NOT parallel)

- `pipeline/nodes/repair.py`: T002, T003, T005, T008, T009 — sequence within the file.
- `pipeline/nodes/evaluate.py`: T006, T010, T012 — in order.
- `pipeline/graph.py`: T007, T011 — in order.
- `tests/integration/test_repair_loop.py`: T016, T017 — same file, in order.

### Parallel opportunities

- T014 (conftest) ∥ T004 (prompt review).
- T015 ∥ T018 (different files) once targets exist.

---

## Implementation Strategy

**MVP = Phase 1 + US1 + US3**: a working, always-terminating repair loop on static errors.
Then US2 adds compiler+sim feedback and the ablation-mode semantics (the research payload),
US4 adds auditability, then tests + polish.

**Token discipline**: all of T001–T017, T019–T020 are offline via mocked LLM. Only T018 spends
real tokens (one run) and self-skips without a key.
