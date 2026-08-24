---
description: "Task list — DUT generation, configurable temperature, human-readable results"
---

# Tasks: DUT Generation, Configurable Temperature & Human-Readable Results

**Feature dir**: `specs/003-dut-gen-and-results`
**Input**: [spec.md](./spec.md) · [plan.md](./plan.md) · [data-model.md](./data-model.md) · [contracts/interfaces.md](./contracts/interfaces.md)
**Working branch**: `phase-2-pyverilog`

Legend: `[P]` = parallelizable (different file, no incomplete deps) · `[USn]` = maps to spec user story.

---

## Phase 1: Governance (blocking prerequisite)

- [x] T001 Amend `.specify/memory/constitution.md`: rewrite Principle IV from "Determinism at Temperature 0" to "Configurable Temperature" — temperature is configurable via `LLM_TEMPERATURE` (default 0.7), robustness comes from tolerant parsing + retry not deterministic decoding; add a one-line Sync Impact note; bump version `1.0.0 → 1.1.0` and update the Last Amended date.

---

## Phase 2: Foundational — LLM config & state schema (blocks all stories)

- [x] T002 Edit `pipeline/config.py`: add `default_temperature: float = field(default_factory=lambda: float(os.environ.get("LLM_TEMPERATURE", "0.7")))` to `PipelineConfig`; add `import os`.
- [x] T003 Edit `pipeline/llm.py`: add `temperature: float | None = None` param to `llm_call`; add `resolve_temperature(temperature)` helper (arg → `LLM_TEMPERATURE` env → 0.7); pass resolved temperature to both `_call_anthropic` and `_call_openai_compat` (replace hardcoded `temperature=0`); thread resolved value through and write it into `log["temperature"]`.
- [x] T004 Edit `pipeline/state.py`: add fields `dut_rtl: str`, `eval_dut_source: Literal["golden", "generated"]`, `scenario_results: list[dict]`; add a comment marking `golden_dut` as optional (eval-only, may be `""`).

**Checkpoint**: `python -c "import pipeline.llm, pipeline.config, pipeline.state"` imports cleanly; `llm_call` accepts `temperature=`.

---

## Phase 3: User Story 1 — Generate testbench from description alone (P1) 🎯 MVP

**Goal**: Pipeline runs with description only; `gen_dut` produces the DUT; downstream consumes it.
**Independent test**: Mocked full-graph run with empty `golden_dut` completes and every node reads the generated `dut_rtl`.

### Implementation

- [x] T005 [P] [US1] Create `prompts/gen_dut.j2`: variables `nl_description`, `circuit_type`, `module_name`; instruct Sonnet to emit ONE synthesizable Verilog module (no testbench, no fences); steer clocked logic when `circuit_type == "SEQ"`.
- [x] T006 [P] [US1] Edit `prompts/classify_circuit.j2`: remove the `golden_dut` variable/section; classify from `nl_description` only; output JSON `{"circuit_type": "CMB"|"SEQ"}` unchanged.
- [x] T007 [US1] Create `pipeline/nodes/gen_dut.py` — `gen_dut_node(state)`: renders `gen_dut.j2` with `nl_description`, `circuit_type`, `module_name`; calls `llm_call(node="gen_dut", model=cfg.model_strong, ...)`; extracts via `extract_code_block(text, "verilog")`; falls back to raw stripped text if empty; returns `{"dut_rtl": ..., "llm_calls": [log]}`. Docstring maps to RQ1/RQ3.
- [x] T008 [US1] Edit `pipeline/nodes/classify.py`: drop the `golden_dut=` kwarg from `render_prompt`.
- [x] T009 [US1] Edit `pipeline/nodes/__init__.py`: export `gen_dut_node`.
- [x] T010 [US1] Edit `pipeline/graph.py`: register `gen_dut` node; replace edge `classify → extract_spec` with `classify → gen_dut → extract_spec`.
- [x] T011 [US1] Edit `pipeline/nodes/extract_spec.py`: render with `golden_dut=state.get("dut_rtl") or state.get("golden_dut", "")` (generated DUT preferred; keep variable name `golden_dut` inside the prompt to avoid template churn, OR rename to `dut` in both — pick one and be consistent).
- [x] T012 [US1] Edit `pipeline/nodes/pyverilog_analysis.py`: pass `state.get("dut_rtl") or state.get("golden_dut", "")` as the DUT to `pyverilog_runner.run(...)` instead of `state["golden_dut"]`.
- [x] T013 [US1] Edit `pipeline/__main__.py`: make `--dut` optional (drop the "both required together" coupling for `--nl`); initialise new state keys `dut_rtl=""`, `eval_dut_source="generated"`, `scenario_results=[]`; leave `golden_dut=""` when none supplied.

**Checkpoint**: mocked run with `golden_dut=""` reaches `evaluate` with a non-empty `dut_rtl`.

---

## Phase 4: User Story 2 — Benchmark against golden DUT at eval only (P2)

**Goal**: When a golden DUT is supplied it is used for evaluation only; generation is unaffected.
**Independent test**: Mocked run with a non-empty `golden_dut` → `eval_dut_source == "golden"`, generation still wrote its own `dut_rtl`.

### Implementation

- [x] T014 [US2] Edit `pipeline/nodes/evaluate.py`: choose eval DUT = `golden_dut` if `state.get("golden_dut","").strip()` else `dut_rtl`; set `updates["eval_dut_source"]`; use the chosen DUT in `icarus.compile_tb`, mutant generation, and `eval2`.
- [x] T015 [US2] Edit `pipeline/nodes/evaluate.py` `_write_result`: add `eval_dut_source` and `dut_rtl` to the persisted result.

**Checkpoint**: mocked run with golden DUT present → result JSON `eval_dut_source == "golden"`; without → `"generated"`.

---

## Phase 5: User Story 3 — Human-readable results (P2)

**Goal**: Persist description + structured scenario outcomes + token totals; print a summary each run.
**Independent test**: `parse_scenarios` unit test + a run showing the summary block.

### Implementation

- [x] T016 [P] [US3] Create `pipeline/reporting.py` — `parse_scenarios(sim_output)` matches `^PASS:\s*<name>` / `^FAIL:\s*<name>` per line, ignores debug lines, returns `[{"name","passed"}]`; `print_run_summary(result)` renders the summary block per contract (description, N/M scenarios + failing names, Eval0/1/2, repair iters, tokens in/out, wall time, status, eval DUT source); both tolerate empty inputs.
- [x] T017 [US3] Edit `pipeline/nodes/evaluate.py`: after simulation, compute `scenario_results = parse_scenarios(sim_out)`; write to state and to the result; in `_write_result` add `nl_description`, `scenario_results`, `scenarios_passed`, `scenarios_total`, `tokens_in_total`, `tokens_out_total` (summed from `llm_calls`).
- [x] T018 [US3] Edit `pipeline/__main__.py`: after `graph.invoke`, load `results/<run_id>.json` (or use `final_state`) and call `print_run_summary(...)`; keep the existing terse `[pipeline]` lines or replace with the summary.

**Checkpoint**: a run prints the summary; result JSON contains `nl_description` + `scenario_results` + token totals.

---

## Phase 6: User Story 4 — Robust at non-zero temperature (P2)

**Goal**: Confirm every LLM-consuming node has a parse fallback so temperature>0 never aborts a run.
**Independent test**: mocked run where a node returns malformed output → run still completes.

### Implementation

- [x] T019 [US4] Audit `pipeline/nodes/{classify,gen_dut,extract_spec,gen_scenarios,gen_checker,error_reasoner}.py`: verify each wraps parsing in try/except with a safe fallback (classify→keyword, extract_spec→`{}`, gen_scenarios→`[]`, gen_dut→raw text, gen_checker→raw text, error_reasoner→`[]`). Add the fallback where missing. No behaviour change when parsing succeeds.

**Checkpoint**: mocked "garbage output" test (T026) passes.

---

## Phase 7: Tests (offline by default; minimal live)

- [x] T020 [P] Create `tests/conftest.py` — `fake_llm` fixture: monkeypatch `pipeline.llm.llm_call` AND the name imported into each node module, returning canned `(text, log)` keyed by `node`; every canned `log` includes `temperature`. Provide canned Verilog/JSON per node so one graph run traverses the whole pipeline.
- [x] T021 [P] Register the `live` marker and skip helper in `pyproject.toml` (`[tool.pytest.ini_options] markers = ["live: hits real LLM API; skipped without key"]`).
- [x] T022 [P] [US4] Create `tests/unit/test_llm_temperature.py`: `resolve_temperature` precedence (arg > env > 0.7); `llm_call` writes `temperature` into the log (with `llm_call` internals mocked at the provider boundary, no network).
- [x] T023 [P] [US1] Create `tests/unit/test_gen_dut.py`: with `fake_llm`, `gen_dut_node` returns non-empty `dut_rtl` and one logged call; empty extraction falls back to raw text.
- [x] T024 [P] [US3] Create `tests/unit/test_reporting.py`: `parse_scenarios` counts PASS/FAIL, ignores debug "failed" lines, handles empty; `print_run_summary` renders with empty `llm_calls` and empty `scenario_results` (capsys).
- [x] T025 [P] [US2] Create `tests/unit/test_evaluate_result.py`: with icarus mocked, result JSON contains `nl_description`, `scenario_results`, `scenarios_passed/total`, `tokens_in_total/out_total`, and correct `eval_dut_source` for golden-present vs golden-absent.
- [x] T026 [US4] Create `tests/integration/test_pipeline_flow_mocked.py`: full `build_graph` runs under `fake_llm` covering — (a) CMB with generated DUT, (b) SEQ path, (c) golden-DUT-present → `eval_dut_source=="golden"`, (d) repair vs evaluate routing via `should_repair` (inject non-empty `error_report`), (e) a node returning malformed output still completes. Assert every node executed and `results/<run_id>.json` written. iverilog/vvp calls mocked or guarded so no real simulation is required.
- [x] T027 [P] Create `tests/integration/test_live_api.py`: `@pytest.mark.live`, `skipif` no `ANTHROPIC_API_KEY`/`LLM_API_KEY`; 1 real end-to-end run on `half_adder` asserting `final_status` set and `llm_calls[*].temperature` present.

**Checkpoint**: `pytest -q` green with NO API key; `pytest -m live` skipped without key.

---

## Phase 8: Polish

- [x] T028 Run full `pytest -q` offline; fix failures.
- [x] T029 Update `docs/research-log.md`: mark this feature done, note Constitution v1.1.0, DUT-generation flow, results summary.
- [x] T030 [P] Update `README.md` / `demo_commands.md` usage: description-only runs, `LLM_TEMPERATURE`, benchmark-with-golden-DUT.

---

## Dependencies & Execution Order

- **Phase 1 (T001)** governance — do first (unblocks the temperature change conceptually).
- **Phase 2 (T002–T004)** foundational — blocks everything below.
- **Phase 3 (US1)** MVP — the core flow; T005/T006 parallel, then T007–T013 sequential-ish (graph + node wiring).
- **Phase 4 (US2)** depends on US1 (`dut_rtl` exists) + T004.
- **Phase 5 (US3)** depends on evaluate edits from US2 touching the same file (T014/T015 before T017).
- **Phase 6 (US4)** independent audit; can run alongside Phase 5.
- **Phase 7 (Tests)** after the code they cover exists; T020/T021 first (fixtures/markers), then unit tests [P], then T026 integration.
- **Phase 8** last.

### Parallel opportunities

- T005 + T006 (two prompt files).
- T022 + T023 + T024 + T025 (separate unit test files) once their targets exist.
- T027 alongside T026.

### Same-file cautions (NOT parallel)

- `pipeline/nodes/evaluate.py`: T014, T015, T017 all edit it — do in order.
- `pipeline/__main__.py`: T013 and T018 — do in order.
- `pipeline/graph.py`: T010 only.

---

## Implementation Strategy

**MVP = Phase 1 + 2 + 3 (US1).** Delivers the headline capability: run from a description with no golden DUT. Demo it, then layer US2 (benchmark eval), US3 (readable results), US4 (robustness), then tests + polish.

**Token discipline**: every task above is implementable and testable offline via `fake_llm`. Only T027 spends real tokens (one run), and it self-skips without a key.