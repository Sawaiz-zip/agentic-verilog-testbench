# Feature Specification: LangGraph Verilog Testbench Generation Pipeline

**Feature Branch**: `001-langgraph-pipeline`

**Created**: 2026-06-14

**Status**: Phase 1 + Phase 2 Complete — US1 (CMB generation) and US2 (Pyverilog static analysis) both verified 2026-06-24. Phase 3 (repair loop) is next.

**Research context**: S6.ReKI.1 — LLM-Driven Verilog Testbench Generation with Pyverilog-Based Early Error Localization  
**Supervisor**: Bing Wen | **Deadline**: 2026-09-01

---

## User Scenarios & Testing

### User Story 1 — CMB Testbench Generation End-to-End (Priority: P1)

A researcher provides a natural-language description of a combinational circuit and its golden DUT Verilog. The system produces a compilable, functionally correct Verilog testbench that passes against the golden DUT (Eval1) and catches injected mutants (Eval2).

**Why this priority**: This is the core deliverable. Without a working CMB pipeline there is no project.

**Independent Test**: Run the pipeline on `VerilogEval/alu_1bit` (or any simple combinational module). Check: Eval0 (compiles), Eval1 (passes vs golden DUT). No SEQ or repair needed.

**Acceptance Scenarios**:

1. **Given** a NL description of a 1-bit ALU and its golden DUT, **When** the pipeline runs, **Then** a `.v` testbench file is produced that compiles with `iverilog` (Eval0 pass).
2. **Given** the compiled testbench, **When** simulated against the golden DUT with `vvp`, **Then** the simulation exits with no assertion failures (Eval1 pass).
3. **Given** the pipeline finishes, **When** the run log is inspected, **Then** every LLM call has a recorded `{node, model, tokens_in, tokens_out, latency_ms, run_id}`.

---

### User Story 2 — Pyverilog Static Analysis & Error Reporting (Priority: P2)

After testbench generation, the system runs Pyverilog on the TB + golden DUT pair and produces a structured error report `{error_type, affected_signal, line, suggested_fix, severity}` covering port-binding mismatches, undriven inputs, unobserved outputs, and sensitivity-list issues.

**Why this priority**: This is the primary research contribution (RQ1, RQ2). Without it the project is just a reimplementation of AutoBench.

**Independent Test**: Feed a hand-crafted buggy testbench (wrong port name) into the Pyverilog analysis node alone and assert the error report contains `error_type: port_binding_mismatch`.

**Acceptance Scenarios**:

1. **Given** a testbench with a miswired port (`clk` connected to `reset`), **When** the Pyverilog node runs, **Then** the error report contains `{error_type: "port_binding_mismatch", affected_signal: "clk", severity: "ERROR"}`.
2. **Given** a testbench with a missing `$monitor` / `$fdisplay` for a SEQ output, **When** the Pyverilog node runs, **Then** the report contains `{error_type: "missing_fdisplay", severity: "WARNING"}`.
3. **Given** a syntactically invalid TB that Pyverilog cannot parse, **When** the Pyverilog node runs, **Then** Verible is automatically used as fallback and the report notes `parser: verible`.
4. **Given** a fully correct testbench, **When** the Pyverilog node runs, **Then** the error report is empty and the node completes without entering the repair loop.

---

### User Story 3 — LLM-Guided Repair Loop (Priority: P3)

When the Pyverilog error report is non-empty and `repair_iter < max_repair_iter`, the system feeds the structured error report back to the LLM (Sonnet) and regenerates the driver and/or checker. The loop detects oscillation and exits gracefully.

**Why this priority**: Repair is what differentiates the system from a single-shot generator (RQ3). It depends on US1 + US2.

**Independent Test**: Inject a known port-binding error into a generated testbench. Assert the pipeline produces a corrected testbench within 2 iterations and that `repair_iter ≤ 2` is recorded in the run log.

**Acceptance Scenarios**:

1. **Given** a testbench with a port error and `max_repair_iter=3`, **When** the repair loop runs, **Then** the LLM receives the Pyverilog error report as structured context and regenerates the driver.
2. **Given** the same error appears in two consecutive iterations, **When** the oscillation detector runs, **Then** `oscillation_detected=True` is set and the loop exits without further LLM calls.
3. **Given** the repair succeeds, **When** the final Icarus Verilog evaluation runs, **Then** Eval0 passes.
4. **Given** all `max_repair_iter` iterations are exhausted without Eval0 passing, **When** the pipeline ends, **Then** `final_status="exhausted_iters"` is recorded.

---

### User Story 4 — SEQ Circuit Support with Deterministic Standardiser (Priority: P4)

Sequential circuits are handled by the same pipeline with an additional standardiser node that inserts missing `$fdisplay` / `$monitor` statements via a Python AST pass (never via LLM).

**Why this priority**: SEQ is the hard case (AutoBench only achieves 26% Eval2). Comes after CMB pipeline is solid.

**Independent Test**: Feed a SEQ testbench missing `$fdisplay` for its output register into the standardiser node alone. Assert the output file contains `$fdisplay` without any LLM call being made.

**Acceptance Scenarios**:

1. **Given** a SEQ testbench missing `$fdisplay`, **When** the standardiser runs, **Then** the output Verilog contains `$fdisplay` for every output signal and no LLM call is logged for this node.
2. **Given** a circuit classified as SEQ, **When** the full pipeline runs, **Then** `circuit_type="SEQ"` is in the state and the standardiser node is executed before Pyverilog analysis.
3. **Given** a SEQ testbench that already has `$fdisplay`, **When** the standardiser runs, **Then** the file is unchanged (idempotent).

---

### User Story 5 — Ablation Evaluation & Failure Attribution (Priority: P5)

The pipeline runs in four modes controlled by a config flag: `baseline` (no repair), `compiler_only` (repair on iverilog errors), `pyverilog_only` (repair on static errors), and `hybrid` (both). Per-node failure counts and token costs are exported as a JSON summary.

**Why this priority**: This produces the empirical results for RQ3 and RQ4. Depends on all prior user stories.

**Independent Test**: Run all four modes on 5 CMB modules and verify the JSON summary has distinct `eval2_pass_rate` values across modes and that `llm_calls` token counts are present.

**Acceptance Scenarios**:

1. **Given** `mode=baseline`, **When** the pipeline runs, **Then** no repair loop is entered regardless of errors.
2. **Given** `mode=hybrid`, **When** Pyverilog finds errors, **Then** the LLM is called for repair before Icarus Verilog simulation.
3. **Given** a pipeline run completes, **When** the JSON summary is inspected, **Then** `failure_stage` is set to the node name where the unrecoverable failure occurred, or `null` on success.
4. **Given** 156 VerilogEval modules are evaluated, **When** results are aggregated, **Then** Eval0/Eval1/Eval2 pass rates and mean token costs per mode are written to `results/summary.json`.

---

### Edge Cases

- What happens when Pyverilog AND Verible both fail to parse the TB? → mark `pyverilog_report.parse_failed=True`, skip static-analysis feedback, proceed to Icarus Verilog directly.
- What if the golden DUT itself is invalid Verilog? → abort with `final_status="invalid_dut"`, log error, do not count toward eval metrics.
- What if the Anthropic API rate-limits mid-run? → exponential backoff (max 3 retries) in the LLM wrapper; log `rate_limit_retries` in telemetry.
- What if `driver_rtl` is empty string after generation? → treat as generation failure, increment `repair_iter`, re-enter repair without running Pyverilog.
- What if a testbench compiles but hangs during simulation? → `vvp` subprocess timeout (default 30 s); log `eval1_timeout=True`.

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST implement the pipeline as a LangGraph state machine with named nodes and conditional edges.
- **FR-002**: System MUST classify each circuit as CMB or SEQ before generating any code (Haiku node).
- **FR-003**: System MUST extract a structured JSON spec (ports, behaviour, timing) from the NL description + golden DUT (Sonnet node).
- **FR-004**: System MUST generate a Verilog driver testbench and a Python checker in parallel LangGraph branches.
- **FR-005**: System MUST run Pyverilog AST + dataflow analysis on the TB + DUT pair before Icarus Verilog simulation.
- **FR-006**: System MUST fall back to Verible if Pyverilog fails to parse the TB.
- **FR-007**: System MUST pass the structured Pyverilog error report to a Sonnet reasoning node that emits `[{error_type, affected_signal, line, suggested_fix, severity}]`.
- **FR-008**: System MUST run the deterministic `$fdisplay` standardiser (Python AST pass) for SEQ circuits before Pyverilog analysis.
- **FR-009**: System MUST implement a repair loop with `max_repair_iter=3` and oscillation detection (`error_report[i] == error_report[i-1]`).
- **FR-010**: System MUST evaluate testbenches with Icarus Verilog: Eval0 (compile), Eval1 (golden DUT pass), Eval2 (mutant discrimination).
- **FR-011**: System MUST log every LLM call with `{node, model, tokens_in, tokens_out, latency_ms, run_id}`.
- **FR-012**: System MUST support four ablation modes via a single config flag: `baseline`, `compiler_only`, `pyverilog_only`, `hybrid`.
- **FR-013**: System MUST write a per-run JSON result including `final_status`, `failure_stage`, `repair_iter`, `llm_calls`, and all eval results.

### Key Entities

- **GraphState**: The LangGraph typed dict holding all pipeline state (see CLAUDE.md §7 for full schema).
- **PyverilogReport**: `{parse_ok, parser_used, port_errors, sensitivity_errors, dataflow_errors, fdisplay_missing, raw_warnings}`.
- **ErrorReport item**: `{error_type, affected_signal, line, suggested_fix, severity}`.
- **LLMCallLog item**: `{node, model, tokens_in, tokens_out, latency_ms, run_id, timestamp}`.
- **RunResult**: `{run_id, module_name, circuit_type, repair_iter, final_status, failure_stage, eval0_pass, eval1_pass, eval2_pass_rate, llm_calls, wall_clock_ms}`.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Eval0 (compilation) pass rate ≥ 90% on the CMB subset of VerilogEval (81 modules) in `hybrid` mode.
- **SC-002**: Eval1 pass rate on CMB subset higher in `hybrid` mode than in `baseline` mode.
- **SC-003**: Eval2 pass rate on CMB subset ≥ AutoBench reported 62.22% in `hybrid` mode (stretch goal; pipeline quality is the primary goal).
- **SC-004**: Pyverilog error precision ≥ 70% and recall ≥ 50% on the hand-labelled dev subset (20 modules).
- **SC-005**: Per-node failure attribution is available for 100% of pipeline runs (no `failure_stage=unknown`).
- **SC-006**: Mean token cost per module is reported and is lower in `pyverilog_only` mode than in `compiler_only` mode.
- **SC-007**: The deterministic standardiser makes `$fdisplay` insertion 100% reliable for SEQ circuits where the output signal is identifiable from the DUT port list.

## Assumptions

- VerilogEval golden DUTs are valid, synthesisable Verilog — no pre-validation of DUTs is performed.
- The Anthropic free-tier API is sufficient for a full pipeline run over 156 modules (rate limits managed via backoff).
- Icarus Verilog and Pyverilog are installed in the development environment; the pipeline does not auto-install them.
- Mutant DUTs for Eval2 are generated by the LLM (Haiku) with a single-line fault injection prompt, consistent with AutoBench's approach.
- The project is developed and evaluated on a single machine (MacOS or Linux); no distributed execution is required.
- Mobile / web UI is out of scope — the pipeline is invoked via CLI (`python -m pipeline run --module <name>`).
