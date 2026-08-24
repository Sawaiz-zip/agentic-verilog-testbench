---
description: "Task list — Sequential (SEQ) circuit support"
---

# Tasks: Sequential (SEQ) Circuit Support

**Feature dir**: `specs/005-seq-support`
**Input**: [spec.md](./spec.md) · [plan.md](./plan.md) · [data-model.md](./data-model.md) · [contracts/interfaces.md](./contracts/interfaces.md)
**Working branch**: `phase-2-pyverilog`

Legend: `[P]` = parallelizable · `[USn]` = maps to spec user story.

---

## Phase 1: User Story 2 — Deterministic standardiser (P1) 🎯 MVP

**Goal**: `insert_fdisplay` guarantees every output is observable + a clock exists; idempotent; no LLM; fail-safe.
**Independent test**: unit tests on the standardiser in isolation.

- [x] T001 [US2] Implement `pipeline/standardiser/fdisplay_inserter.py`:
  `insert_fdisplay(driver_rtl, spec)` + helpers `_find_outputs(spec)`, `_clock_name(spec)`,
  `_is_observed(driver_rtl, name)` (display/monitor/write OR comparison/if), `_has_clock_gen(driver_rtl, clk)`.
  Insert one `$monitor` covering unobserved outputs into the `initial` block; insert
  `always #5 <clk> = ~<clk>;` (+ initial `<clk>=0;`) when a clock is needed and absent; add a
  `// [standardised]` marker for idempotency; wrap the whole body in try/except returning the
  original `driver_rtl` on any error (fail-safe). NO LLM.

**Checkpoint**: `test_fdisplay_inserter.py` (T012) passes.

---

## Phase 2: User Story 1 — Sequential path wired end-to-end (P1)

**Goal**: SEQ circuits route through `standardise` before analysis; the node and graph are live.
**Independent test**: mocked SEQ graph run passes through `standardise` and reaches evaluation.

- [x] T002 [US1] Implement `pipeline/nodes/standardise.py` `standardise_node`: call
  `insert_fdisplay(state["driver_rtl"], state.get("spec") or {})`; return
  `{"driver_rtl": updated}`; zero LLM calls.
- [x] T003 [US1] Create `pipeline/nodes/merge_generation.py` `merge_generation_node(state) -> {}`
  (no-op fan-in barrier); export it from `pipeline/nodes/__init__.py`.
- [x] T004 [US1] Add `route_after_generation(state)` in `pipeline/graph.py` (or repair.py):
  return `"standardise"` if `circuit_type == "SEQ"` else `"pyverilog_analysis"`.
- [x] T005 [US1] Rewire `pipeline/graph.py`: register `merge_generation`; remove
  `gen_driver→pyverilog_analysis` and `gen_checker→pyverilog_analysis`; add
  `gen_driver→merge_generation`, `gen_checker→merge_generation`; add conditional
  `merge_generation → route_after_generation → {standardise, pyverilog_analysis}`; keep
  `standardise → pyverilog_analysis`.
- [x] T006 [US1] Extend `after_repair` in `pipeline/nodes/repair.py`: when continuing (not
  oscillating/exhausted) return `"standardise"` if `circuit_type=="SEQ"` else
  `"pyverilog_analysis"`; add `"standardise"` to the repair conditional-edge map in
  `pipeline/graph.py`.
- [x] T007 [US1] Review `prompts/gen_dut.j2` and `prompts/gen_driver.j2`: confirm SEQ clocking
  guidance (clock generation, reset sequencing, sample-on-edge) is present; tighten wording only
  if a smoke run reveals a gap.

**Checkpoint**: mocked SEQ run traverses `standardise`; CMB run does not; both reach evaluate.

---

## Phase 3: User Story 4 — Sequential fixtures (P2)

**Goal**: a smoke set for the SEQ path.

- [x] T008 [P] [US4] Add `tests/fixtures/seq/dff_prompt.txt` + `dff_ref.v` (D flip-flop:
  `always @(posedge clk) q <= d;`), compile-verified with `iverilog -g2012`.
- [x] T009 [P] [US4] Add `tests/fixtures/seq/counter_4bit_prompt.txt` + `counter_4bit_ref.v`
  (synchronous up counter with reset), compile-verified.
- [x] T010 [P] [US4] Add `tests/fixtures/seq/shift_register_prompt.txt` + `shift_register_ref.v`
  (serial-in shift register), compile-verified.

**Checkpoint**: `iverilog -g2012` compiles all three `_ref.v`.

---

## Phase 4: Tests (offline by default; one live)

- [x] T011 [P] Extend `tests/conftest.py`: add SEQ-coherent canned responses (a clocked
  `gen_dut`, a spec with a clock + one output, and a driver missing the `$monitor` so the
  standardiser visibly acts); expose them so the SEQ routing test can select them.
- [x] T012 [P] [US2] Create `tests/unit/test_fdisplay_inserter.py`: inserts observation for a
  missing output; no-op when all observed; idempotent (`f(f(x))==f(x)`); correct output
  targeting; inserts a clock when absent; fail-safe on malformed input (returns unchanged);
  never emits a DUT/module definition.
- [x] T013 [US1] Create `tests/integration/test_seq_routing.py` (mocked LLM): a SEQ run passes
  through `standardise` (assert via the `// [standardised]` marker or a spy) and ends with all
  outputs observed; a CMB run never enters `standardise`; both complete (no fan-in deadlock).
- [x] T014 [P] Create `tests/integration/test_seq_live.py`: `@pytest.mark.live`, skip without
  key; one real SEQ run (`dff`) reaching a result with `circuit_type=="SEQ"`.

**Checkpoint**: `pytest -q` green offline; `pytest -m live` skipped without key.

---

## Phase 5: Polish

- [x] T015 Run full `pytest -q` offline; fix failures; confirm CMB flow + repair tests still pass (regression).
- [x] T016 Update `docs/research-log.md`: mark SEQ support done; note the standardiser, `merge_generation`
  barrier, SEQ routing, and fixtures.

---

## Dependencies & Execution Order

- **US2 standardiser (T001)** first — MVP; everything observable depends on it.
- **US1 wiring (T002–T007)** next — needs the standardiser to call.
- **US4 fixtures (T008–T010)** parallel with wiring (independent files).
- **Tests (T011–T014)** after their targets exist; T011 (conftest) before T013.
- **Polish (T015–T016)** last.

### Same-file cautions (NOT parallel)

- `pipeline/graph.py`: T005, T006 (edge map) — in order.
- `pipeline/nodes/repair.py`: T006 only.
- `pipeline/nodes/__init__.py`: T003 only.

### Parallel opportunities

- T008 ∥ T009 ∥ T010 (three fixture pairs).
- T012 ∥ T014 (different test files) once targets exist.

---

## Implementation Strategy

**MVP = Phase 1 (T001)**: the deterministic standardiser, independently testable — the core
Principle-VI contribution. Then wire it into the SEQ branch (US1), add fixtures (US4), test, polish.

**Token discipline**: everything is offline/mocked except T014 (one live SEQ run) which
self-skips without a key. Fixtures are verified with `iverilog` (no tokens).
