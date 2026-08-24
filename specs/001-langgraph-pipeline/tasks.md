---
description: "Task list for the LangGraph Verilog testbench pipeline"
---

# Tasks: LangGraph Verilog Testbench Generation Pipeline

**Input**: [spec.md](./spec.md) + [plan.md](./plan.md)
**Last updated**: 2026-06-24

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project skeleton and shared utilities every node depends on. Nothing else can start until this phase is complete.

- [x] T001 Create `pyproject.toml` with dependencies: `langgraph`, `anthropic`, `pyverilog`, `jinja2`, `pytest`
- [x] T002 Create `.env.example` with `ANTHROPIC_API_KEY=` placeholder (updated with all 4 provider options: Groq, Gemini, Ollama, Anthropic)
- [x] T003 [P] Create `pipeline/__init__.py` and package skeleton (`nodes/`, `analysis/`, `standardiser/`, `eval/`)
- [x] T004 Create `pipeline/state.py` — `GraphState` TypedDict matching CLAUDE.md §7 schema exactly (uses `Annotated[list, operator.add]` reducer for llm_calls to support parallel branch merging)
- [x] T005 Create `pipeline/config.py` — `AblationMode` enum (`BASELINE`, `COMPILER_ONLY`, `PYVERILOG_ONLY`, `HYBRID`) and `PipelineConfig` dataclass
- [x] T006 Create `pipeline/llm.py` — multi-provider LLM wrapper (Anthropic > compat/Groq > OpenAI); logs `{node, model, tokens_in, tokens_out, latency_ms, run_id}`; exponential backoff; temperature=0
- [x] T007 Create `pipeline/graph.py` — LangGraph graph with all 10 nodes registered and all edges wired
- [x] T008 [P] Create `tests/` directory structure: `unit/`, `integration/`, `fixtures/cmb/`, `fixtures/seq/`
- [x] T009 [P] Add 5 hand-picked CMB fixtures to `tests/fixtures/cmb/` (`alu_1bit`, `mux2to1`, `half_adder`, `comparator_2bit`, `priority_encoder`) — all verified to compile with `iverilog -g2012`
- [x] T010 [P] Verify `iverilog --version` and `pyverilog` importable; add `scripts/check_env.sh`

**Checkpoint**: `python -m pipeline --help` works; `pytest tests/unit/` collects 0 tests without error.

---

## Phase 2: Foundational LangGraph Nodes (User Story 1 — CMB pipeline)

**Purpose**: Core generation path for combinational circuits. Blocks all user-story work.

**⚠️ CRITICAL**: No repair or Pyverilog work can begin until Phase 2 checkpoint passes.

### 2a — Prompt Templates

- [x] T011 [P] Create `prompts/classify_circuit.j2` — inputs: `nl_description`, `golden_dut`; instructs Haiku to output JSON `{"circuit_type": "CMB"|"SEQ"}`
- [x] T012 [P] Create `prompts/extract_spec.j2` — inputs: `nl_description`, `golden_dut`; instructs Sonnet to output JSON spec `{ports, behaviour, timing}`
- [x] T013 [P] Create `prompts/gen_scenarios.j2` — inputs: `spec`; instructs Haiku to output list of named test scenarios `[{name, inputs, expected}]` (added STRICT RULES prohibiting X/Z and out-of-range values)
- [x] T014 [P] Create `prompts/gen_driver.j2` — inputs: `spec`, `scenarios`, `module_name`, `golden_dut`; instructs Sonnet to output Verilog testbench driver (added PASS:/FAIL: marker requirements)
- [x] T015 [P] Create `prompts/gen_checker.j2` — inputs: `spec`, `scenarios`, `module_name`; instructs Sonnet to output Python checker script
- [x] T016 [P] Create `prompts/gen_mutant.j2` — inputs: `golden_dut`, `module_name`; instructs Haiku to output a single-line fault-injected Verilog mutant

### 2b — Node Implementations

- [x] T017 Create `pipeline/nodes/classify.py` — calls `llm_call()` with Haiku + `classify_circuit.j2`; writes `circuit_type` to state; keyword fallback on JSON parse error
- [x] T018 Create `pipeline/nodes/extract_spec.py` — calls `llm_call()` with Sonnet + `extract_spec.j2`; writes `spec` dict to state
- [x] T019 Create `pipeline/nodes/gen_scenarios.py` — calls `llm_call()` with Haiku + `gen_scenarios.j2`; writes `scenarios` list to state
- [x] T020 [P] Create `pipeline/nodes/gen_driver.py` — calls `llm_call()` with Sonnet + `gen_driver.j2` (max_tokens=8192); includes error_report from state for repair iterations
- [x] T021 [P] Create `pipeline/nodes/gen_checker.py` — calls `llm_call()` with Sonnet + `gen_checker.j2`; extracts Python code block
- [x] T022 Wire parallel branches in `pipeline/graph.py`: gen_driver and gen_checker run in parallel after gen_scenarios

### 2c — Evaluation

- [x] T023 Create `pipeline/eval/icarus.py` — `compile_tb(driver_rtl, dut_rtl) -> (bool, str, str)` and `simulate_tb(compiled_path, timeout_s=30) -> (bool, str)`; handles subprocess timeout; failure detection uses `re.search(r'\bFAIL\s*:', output)` to avoid false positives
- [x] T024 Create `pipeline/eval/mutant_gen.py` — calls `llm_call()` with Haiku + `gen_mutant.j2`; generates N mutant DUTs
- [x] T025 Add Eval2 logic to `pipeline/eval/icarus.py`: run TB against each mutant DUT; skip mutants that don't compile (invalid, not caught); compute `eval2_pass_rate`
- [x] T026 Create `pipeline/nodes/evaluate.py` — orchestrates Eval0 → Eval1 → Eval2; writes all eval fields + debug fields to state

### 2d — Results Logging

- [x] T027 Create `pipeline/nodes/evaluate.py` result-serialisation: write `RunResult` JSON to `results/<run_id>.json` after every run (includes debug fields: driver_rtl, compiler_output, sim_output when Eval0/Eval1 fails)

**Checkpoint**: ✅ PASSED (2026-06-24) — Eval0 5/5=100%, Eval1 4/5=80%, Eval2 4/4=100%. All runs produce `results/<run_id>.json` with `llm_calls` populated. One Eval1 failure (priority_encoder) is a prompt/hallucination issue — repair loop (Phase 4) will address.

---

## Phase 3: User Story 2 — Pyverilog Static Analysis

**Goal**: Add the pre-simulation error-localisation layer (primary research contribution).

**Independent Test**: `pytest tests/unit/test_pyverilog_runner.py` with a hand-crafted buggy TB → error report contains expected `error_type`.

### Tests for User Story 2

- [x] T028 [P] [US2] Write `tests/unit/test_pyverilog_runner.py`: 8 tests covering port-binding mismatch (missing port, wrong name), clean TB, parse_ok, JSON serialisable, SEQ correct TB, wrong sensitivity list, missing $fdisplay
- [x] T029 [P] [US2] Write `tests/unit/test_error_taxonomy.py`: 6 tests — all ErrorType constants, severity values, ErrorReportItem.to_dict(), PyverilogReport.is_clean() (clean + dirty), PyverilogReport.to_dict() structure

### Implementation for User Story 2

- [x] T030 [US2] Create `pipeline/analysis/error_taxonomy.py` — `ErrorType` enum + `PyverilogReport` dataclass + `ErrorReportItem` dataclass (done in Phase 1 skeleton, was never a stub)
- [x] T031 [US2] Create `pipeline/analysis/pyverilog_runner.py` — parse TB + DUT together; `_check_port_bindings()` (AST); `_check_driven_observed()` (text heuristics for undriven/unobserved); `_check_sensitivity_lists()` (AST, SEQ only); `_check_fdisplay()` (SEQ only); Verible fallback on parse error
- [x] T032 [US2] Create `pipeline/analysis/verible_runner.py` — `verible-verilog-syntax --export_json -` subprocess; returns `parse_ok=False` gracefully when not installed
- [x] T033 [US2] Create `prompts/error_reasoner.j2` — done in Phase 1 skeleton; inputs: `pyverilog_report`, `spec`, `driver_rtl`; outputs JSON error list
- [x] T034 [US2] Create `pipeline/nodes/pyverilog_analysis.py` — calls pyverilog_runner.run(); Verible fallback if parse_ok=False; zero LLM calls; writes pyverilog_report dict to state
- [x] T035 [US2] Create `pipeline/nodes/error_reasoner.py` — snapshots last_error_report; skips LLM call if pyverilog_report clean (saves tokens); otherwise calls Sonnet + error_reasoner.j2
- [x] T036 [US2] Wire Pyverilog node into graph: already wired in Phase 1 skeleton (stubs replaced by full implementation)

**Checkpoint**: ✅ PASSED (2026-06-24) — 17/17 unit tests pass; buggy TB with wrong port name → non-empty error_report; half_adder pipeline gate: success, error_reasoner 0 LLM calls on clean TB.

---

## Phase 4: User Story 3 — Repair Loop

**Goal**: Feed error reports back to LLM and regenerate until fixed or exhausted.

**Independent Test**: Run pipeline on CMB fixture with injected port error; assert `repair_iter ≤ 2` and final TB compiles.

### Tests for User Story 3

- [ ] T037 [P] [US3] Write `tests/integration/test_repair_loop.py`: inject known port-binding error; verify pipeline repairs it within 2 iterations; verify oscillation detection terminates loop when same error repeats

### Implementation for User Story 3

- [ ] T038 [US3] Create `prompts/repair_driver.j2` — inputs: `driver_rtl`, `error_report`, `spec`, `scenarios`; instructs Sonnet to output corrected Verilog driver
- [ ] T039 [US3] Create `pipeline/nodes/repair.py` — oscillation check (`error_report == last_error_report`); sets `oscillation_detected`; increments `repair_iter`; routes to gen_driver/gen_checker or evaluate
- [ ] T040 [US3] Add conditional edge `should_repair()` to `pipeline/graph.py`: returns `"repair"` if `error_report non-empty AND repair_iter < max_repair_iter AND NOT oscillation_detected`, else `"evaluate"`
- [ ] T041 [US3] Wire `AblationMode` into conditional edges: in `BASELINE` mode `should_repair()` always returns `"evaluate"`; in `COMPILER_ONLY` repair triggers only on compile failure; in `PYVERILOG_ONLY` repair triggers only on Pyverilog errors; in `HYBRID` both trigger repair

**Checkpoint**: Integration test passes. `final_status` correctly set to `"oscillated"` or `"exhausted_iters"` in failure cases.

---

## Phase 5: User Story 4 — SEQ Support + Deterministic Standardiser

**Goal**: Handle sequential circuits with `$fdisplay` insertion via Python AST pass.

**Independent Test**: `pytest tests/unit/test_fdisplay_inserter.py` with SEQ TB missing `$fdisplay` → output contains `$fdisplay`; no LLM call logged.

### Tests for User Story 4

- [ ] T042 [P] [US4] Write `tests/unit/test_fdisplay_inserter.py`: test insertion, idempotency, and correct targeting of output signals
- [ ] T043 [P] [US4] Add 5 SEQ fixtures to `tests/fixtures/seq/` (e.g., `dff`, `counter_4bit`, `shift_register`, `fsm_traffic_light`, `accumulator`)

### Implementation for User Story 4

- [ ] T044 [US4] Create `pipeline/standardiser/fdisplay_inserter.py` — Python-only AST walk: locate all DUT output ports; verify `$fdisplay` or `$monitor` exists for each; insert missing ones at end of always block; return modified Verilog string; zero LLM calls
- [ ] T045 [US4] Create `pipeline/nodes/standardise.py` — calls `fdisplay_inserter.py`; writes updated `driver_rtl` to state; logs 0 LLM calls for this node
- [ ] T046 [US4] Add SEQ conditional branch in `pipeline/graph.py`: after classify, if `circuit_type=="SEQ"` route through standardise node before pyverilog_analysis
- [ ] T047 [US4] Run SEQ smoke set (5 fixtures) through full pipeline; verify standardiser makes all SEQ fixtures hit Eval0

**Checkpoint**: SEQ smoke set Eval0 ≥ 90%. `$fdisplay` log confirms zero LLM calls for standardise node.

---

## Phase 6: User Story 5 — Ablation Evaluation & Failure Attribution

**Goal**: Run full 156-module VerilogEval evaluation across all 4 modes and produce summary results.

**Independent Test**: Run all 4 modes on 5 CMB smoke modules; verify `results/summary.json` has 4 entries with distinct `eval2_pass_rate` values.

### Tests for User Story 5

- [ ] T048 [P] [US5] Write `tests/integration/test_cmb_pipeline.py`: end-to-end on 5 CMB fixtures across all 4 ablation modes; assert `results/<run_id>.json` exists and has required fields

### Implementation for User Story 5

- [ ] T049 [US5] Create `scripts/run_eval.sh` — runs pipeline over all 156 VerilogEval modules for a given `AblationMode`; saves individual `results/<run_id>.json` per module
- [ ] T050 [US5] Create `scripts/aggregate_results.py` — reads all `results/*.json`; computes Eval0/Eval1/Eval2 pass rates, mean repair_iter, mean token cost per mode; writes `results/summary.json`
- [ ] T051 [US5] Run full evaluation: 4 modes × 156 modules = 624 pipeline runs
- [ ] T052 [US5] Generate failure attribution table: for each `failure_stage` value, count occurrences and compute fraction; add to `results/summary.json`
- [ ] T053 [US5] Measure Pyverilog error precision and recall on 20-module hand-labelled dev set; add to `results/summary.json`

**Checkpoint**: `results/summary.json` exists with all 4 modes, Eval0/1/2 rates, per-node failure counts, and token costs.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T054 [P] Add `__main__.py` CLI entry point: `python -m pipeline run --module <name> --mode hybrid` (supports VerilogEval exact/partial match + fixture fallback)
- [x] T055 [P] Write `scripts/run_smoke.sh` for fast 5-module CMB validation
- [ ] T056 Add `docs/research-log.md` updates at each phase checkpoint
- [ ] T057 [P] Run `pytest` full suite and fix all failures
- [ ] T058 Add `results/` to `.gitignore`
- [ ] T059 Final LaTeX report: pipeline diagram, ablation table, failure attribution figure, error taxonomy table

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (CMB Generation)**: Depends on Phase 1 — blocks all user stories
- **Phase 3 (Pyverilog)**: Depends on Phase 2 checkpoint passing
- **Phase 4 (Repair Loop)**: Depends on Phase 3 checkpoint passing
- **Phase 5 (SEQ)**: Depends on Phase 2 checkpoint — CMB must be solid first
- **Phase 6 (Evaluation)**: Depends on Phases 3, 4, 5 all complete
- **Phase 7 (Polish)**: Depends on Phase 6

### Parallel Opportunities

- T011–T016 (all prompt templates) can be written in parallel
- T020/T021 (gen_driver / gen_checker nodes) can be written in parallel — they are separate LangGraph branches
- T028/T029 (US2 unit tests) can be written in parallel with T030 (error taxonomy)
- T042/T043 (US4 tests + fixtures) can be written in parallel
- T054/T055/T057/T058 (polish tasks) can all run in parallel

### Critical Path

Phase 1 → Phase 2 (T017–T027) → Phase 3 (T030–T036) → Phase 4 (T038–T041) → Phase 6 (T051–T053) → Phase 7 (T059)

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup)
2. Complete Phase 2a–2d (CMB generation + eval)
3. Run smoke set → validate Eval0 ≥ 80%
4. Stop and demo: "pipeline generates and evaluates a CMB testbench"

### Incremental Delivery

1. Setup + CMB → smoke validated → MVP demo
2. Add Pyverilog layer → error reports working → Precision/recall measured
3. Add repair loop → repair integration test passes
4. Add SEQ support → SEQ smoke passes
5. Full evaluation → summary.json produced → report written

---

## Notes

- `[P]` = can run in parallel (no shared file conflicts)
- `[US*]` = maps to user story for traceability
- Constitution check must pass mentally before starting any node implementation
- Commit after each task or logical group
- Avoid: vague tasks, same-file conflicts, cross-story dependencies that break independence
- **Do not install dependencies or run code until pyproject.toml is committed** (per CLAUDE.md §15)
