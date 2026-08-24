# Project Context — S6.ReKI.1

> **For future Claude sessions:** This file is the single source of truth for this research project.
> Read it first. Then check `PROGRESS.md` for current status.
> Do not re-derive anything from `paper.pdf` unless explicitly asked — the summary below is authoritative.

---

## 1. Project Metadata

| Field | Value |
|---|---|
| **Topic ID** | S6.ReKI.1 |
| **Title** | LLM-Driven Verilog Testbench Generation with Pyverilog-Based Early Error Localization |
| **Student** | Muhammad Sawaiz Naveed |
| **Student email** | muhammad-sawaiz.naveed@tu-ilmenau.de |
| **Supervisor** | Bing Wen — wen.bing@tu-ilmenau.de |
| **University** | Technische Universität Ilmenau |
| **Final report deadline** | September 1, 2026 |
| **Working directory** | `/Users/sawaiznaveed/Ilmenau Uni/ResearchProject` |

---

## 2. Project Description (from professor)

Students will engage with research on automatic Verilog generation using LLMs, study Pyverilog and Icarus Verilog, examine current research using Pyverilog for functional error detection, learn how to generate Verilog from natural-language descriptions via LLM APIs, and **investigate how Pyverilog and/or LLM-based methods can be used for early error localization in LLM-generated Verilog** — making it possible to detect, narrow down, and localize errors in automatically generated Verilog as early as possible.

---

## 3. Core Idea (one paragraph)

LLMs can generate Verilog testbenches from natural language but the output is often **functionally wrong while being syntactically valid** — the simulator compiles it yet the testbench fails to exercise the DUT correctly (wrong port bindings, missing `$fdisplay`, bad sensitivity lists, off-by-one scenarios). The standard remedy is to run a full simulation and inspect the result, which is a slow feedback loop. This project develops a **graph-based LLM workflow for Verilog testbench generation** with a **Pyverilog-based pre-simulation analysis layer** that localises common errors immediately and feeds structured guidance back to the LLM. The pipeline is implemented as a **LangGraph** state machine with explicit nodes, conditional edges, and a repair loop. The accent is on **pipeline architecture and per-node behaviour**, not on chasing peak benchmark scores — the free-tier Claude API is sufficient.

---

## 4. AutoBench Paper Summary (arXiv:2407.03891)

**Authors:** Qiu, Zhang, Drechsler, Schlichtmann, Li (TUM, Bremen, Siegen) — MLCAD 2024

### Methods

The paper splits LLM-based testbench generation into a multi-stage pipeline:

| Stage | Purpose |
|---|---|
| **Stage 0** | Classify circuit as combinational (CMB) or sequential (SEQ) using LLM-generated sample RTL + regex check for `always@(posedge ...)` |
| **Stage 1** | LLM produces structured JSON spec (ports, behaviours, timing) |
| **Stage 2** | LLM generates list of named test scenarios (driver track) |
| **Stage 3** | LLM generates Python core checking rules (checker track) |
| **Stage 4** | LLM generates Verilog driver; for SEQ, two sub-steps (architecture + `$fdisplay` insertion) |
| **Stage 5** | LLM generates Python checker reading TBout.txt, returns failed scenarios |

### Self-Enhancement
- **Scenario checking** — Python verifies all Stage-2 scenarios appear in driver (max 3 retries)
- **Auto-debug** — feed compiler errors + line-numbered code to LLM (max 1 attempt)
- **Reboot** — regenerate from Stage 4/5 if debug fails (max 5 total)
- **Code standardization** — Python script forcibly inserts missing `$fdisplay` for SEQ

### AutoEval (their evaluation framework)
- **Eval0** — code compiles
- **Eval1** — passes against golden RTL
- **Eval2** — matches golden testbench on ~10 LLM-generated mutants (≥80% match = pass)

### Results

| Group | Eval2 pass@1 | vs Baseline |
|---|---|---|
| Total (156 tasks) | 44.81% | +57% over 28.46% |
| Combinational (81) | 62.22% | +31% over 47.65% |
| Sequential (75) | **26.00%** | **+3.36×** over 7.73% |

**Eval0 pass@1 (compilation):** 95.71% (theirs) vs 70.06% (baseline). For SEQ alone: 97.33% vs 55.47% — driven mostly by their standardization script.

### Gaps the paper leaves (our opportunity)
- Sequential circuits remain weak (26% Eval2)
- Only tested with GPT-4-turbo — no cross-model study
- No per-stage failure attribution
- No cost or latency analysis
- The `$fdisplay` standardization is partly LLM-based and fragile
- Focuses on **testbench generation**, not error localization in the **RTL itself**

---

## 5. Our Approach — Decisions Made

| Decision | Rationale |
|---|---|
| **Testbench generation as the subject** | Matches Prof. Wen's official S6.ReKI.1 description ("generate, refine, and validate HDL testbenches") |
| **Pipeline > accuracy** | Supervisor explicitly prioritises pipeline architecture over raw benchmark numbers; free-tier API is fine |
| **LangGraph** for orchestration | Explicit graph, conditional edges, feedback loops as first-class constructs — better than imperative scripts |
| **Claude API free tier** (Sonnet + Haiku) | Free tier is sufficient given pipeline-first priority; Haiku for cheap classification, Sonnet for code |
| **Pyverilog** for static analysis | AST + dataflow + control-flow; no simulation needed |
| **Verible fallback** | Backup parser when Pyverilog rejects LLM output (it sometimes does) |
| **Icarus Verilog** for ground-truth eval | Standard, free, IEEE 1800-2012 |
| ~~**VerilogEval as primary dataset**~~ → **12-circuit hard set** (2026-08-24) | The full 156 is not funded. Replaced by 12 circuits (6 easy / 6 hard, 6 CMB / 6 SEQ) × 5 modes × 2 repeats. Deliberately harder circuits, because four of five static checks cannot fire on 8–17 line fixtures. |
| **CMB first, SEQ later** | Iterate fast on the easier case; SEQ is where AutoBench struggles |
| **Deterministic standardizer** for SEQ | Replace AutoBench's fragile LLM-based `$fdisplay` insertion with a Python parser |
| **Model routing per node** | Haiku for classification/scenarios, Sonnet for code generation/debugging |
| **Parallel Driver + Checker tracks** | Independent branches in LangGraph; cuts wall-clock time |
| **Held-out test split (80%)** | Prevent prompt overfitting; freeze prompts before final eval |

---

## 6. Pipeline Architecture

```
INPUT: NL circuit description + golden DUT (Verilog)
   │
   ▼
[1] Multi-stage Testbench Generation
       1a. classify CMB/SEQ (Haiku)
       1b. extract structured JSON spec (ports, behaviour, timing)
       1c. generate named scenario list (driver track)
       1d. generate Verilog driver code
       1e. generate Python checker (checker track)
       (1d and 1e can run in parallel branches)
   │
   ▼
[2] Pyverilog Static Analysis  (deterministic, no simulation)
       parse TB + golden DUT together
       AST: port bindings (TB ↔ DUT), sensitivity lists
       Dataflow: undriven inputs, unobserved outputs, width mismatches
       Presence: $fdisplay for every output (SEQ)
       Verible fallback if Pyverilog rejects the file
   │
   ▼
[3] LLM Error Reasoner  (Sonnet) — Pyverilog report + spec → error list
       {error_type, affected_signal, line, suggested_fix}
   │
   ▼
[4] Deterministic Standardizer (Python AST pass)
       insert missing $fdisplay; normalise clocking
   │
   ▼
[5] Repair Loop  (max N=3 iterations; oscillation detection)
       errors → re-prompt LLM with error report → regenerate → re-analyze
   │
   ▼
[6] Icarus Verilog Evaluation
       Eval0: compile
       Eval1: TB passes against golden DUT
       Eval2: TB distinguishes golden DUT from LLM-generated mutants
   │
   ▼
OUTPUT (testbench + error trace + per-node iteration log)
```

**Feedback edges:**
- After [3]: if errors found and `repair_iter < 3` → loop back to [1d/1e] with error context
- After [6]: if compile fails → re-enter [5] once more
- Oscillation: if `error_report[i] == error_report[i-1]` → break loop

---

## 7. LangGraph State Schema

```python
class GraphState(TypedDict):
    # Inputs
    nl_description: str
    module_name: str
    golden_dut: str                # Verilog source of the DUT
    mutant_duts: list[str]         # for Eval2

    # Stage outputs
    circuit_type: Literal["CMB", "SEQ"]
    spec: dict                     # JSON spec (ports, behaviour, timing)
    scenarios: list[dict]          # [{name, inputs, expected}]
    driver_rtl: str                # generated Verilog testbench/driver
    checker_py: str                # generated Python checker
    pyverilog_report: dict         # AST + dataflow + port-binding summary
    error_report: list[dict]       # [{type, signal, line, suggested_fix, severity}]
    last_error_report: list[dict]  # for oscillation detection

    # Loop control
    repair_iter: int
    max_repair_iter: int           # default 3
    oscillation_detected: bool

    # Evaluation
    eval0_pass: bool               # compiles
    eval1_pass: bool               # passes vs golden DUT
    eval2_pass_rate: float         # fraction of mutants caught
    failure_stage: str | None      # which node produced the unrecoverable error
    final_status: Literal["success", "failed_compile", "failed_eval1",
                          "failed_eval2", "oscillated", "exhausted_iters"]

    # Telemetry
    run_id: str
    llm_calls: list[dict]          # {node, model, tokens_in, tokens_out, latency_ms}
```

---

## 8. Research Questions

- **RQ1.** What categories of functional errors appear most frequently in LLM-generated Verilog **testbenches**, and which of these are detectable without full simulation?
- **RQ2.** To what extent can Pyverilog's AST and dataflow analysis (port bindings, sensitivity lists, dataflow consistency between testbench and DUT) narrow down testbench errors prior to simulation?
- **RQ3.** Can an LLM, informed by Pyverilog analysis results, effectively localise and repair testbench errors, and how does this compare to using only compiler/simulator feedback as in prior work?
- **RQ4.** What is the cost–quality tradeoff of combining lightweight static analysis with LLM reasoning vs relying solely on compiler/simulator feedback for repair?

---

## 9. Expected Contributions

1. **LangGraph testbench-generation pipeline** — open-source, modular, graph-based workflow with explicit nodes for classification, spec extraction, scenario generation, driver/checker generation, static analysis, error reasoning, standardisation, repair, and evaluation. This is the primary contribution and matches the project description's focus on graph-based LLM workflows.
2. **Pyverilog-based pre-simulation error localiser** — reusable Python module converting Pyverilog AST/dataflow output into structured, LLM-readable summaries focused on testbench-DUT interaction errors.
3. **Deterministic `$fdisplay` standardiser** — Python AST pass that replaces AutoBench's fragile LLM-based standardisation step.
4. **Testbench-error taxonomy** — categorised catalogue of testbench error types with frequency and Pyverilog detectability, bootstrapped on a hand-labelled dev subset.
5. **Per-node failure attribution** — empirical breakdown of where failures originate in the 6-stage pipeline, enabled for free by LangGraph logging (AutoBench does not provide this).
6. **Empirical comparison of feedback strategies** — baseline, retry-only (control), compiler-only, Pyverilog-only, and hybrid, across CMB and SEQ benchmarks. The `retry_only` arm is what makes the comparison sound: every repairing mode gets an extra LLM sample that baseline does not, so without it a gain cannot be attributed to the feedback.

---

## 10. Evaluation Metrics

| Metric | Description |
|---|---|
| **Eval0** | Testbench compilation pass rate (Icarus Verilog) |
| **Eval1** | Testbench passes against golden DUT |
| **Eval2** | Testbench distinguishes golden DUT from LLM-generated mutants |
| **Error precision** | Pyverilog-flagged errors that are real |
| **Error recall** | Real errors that Pyverilog catches |
| **Per-node failure attribution** | Distribution of failures over the 6 pipeline stages |
| **Iterations to pass** | Distribution of repair iterations needed |
| **Tokens per module** | LLM cost per generated testbench |

**Ablations (5 modes):** `baseline` (no repair) | `retry_only` (one extra sample, **zero diagnostics** — the control) | `compiler_only` | `pyverilog_only` | `hybrid` (ours).

A mode must beat **`retry_only`**, not merely `baseline`, before its feedback can be claimed to work.

---

## 11. Timeline (5 phases, 20 weeks → Sept 1, 2026)

| Phase | Weeks | Focus |
|---|---|---|
| **0 — Setup** | 1–2 (May 2026) | Literature, dev env, dataset analysis |
| **1 — Generation** | 3–6 (May–Jun) | LangGraph skeleton, LLM Verilog generation for CMB, Eval0/Eval1 integration |
| **2 — Pyverilog** | 5–9 (Jun) | AST + dataflow module, error taxonomy, LLM reasoning node |
| **3 — Repair + SEQ** | 10–13 (Jun–Jul) | Repair loop, sequential circuit support, full integration |
| **4 — Evaluation** | 14–16 (Jul–Aug) | Ablations on test set, failure-mode analysis, cost analysis |
| **5 — Writing** | 17–20 (Aug–Sep) | Final report, revision, submission |

---

## 12. References (annotated)

| Citation | arXiv | One-line description |
|---|---|---|
| Foster 2022 | — | Wilson Research Group functional verification industry survey (60% effort on verification) |
| Liu 2023 — VerilogEval | 2309.07544 | Benchmark of 156 Verilog problems from HDLBits; standard eval dataset |
| Qiu 2024 — AutoBench | **2407.03891** | The seed paper — multi-stage LLM testbench generation with self-enhancement |
| Takamaeda 2015 — Pyverilog | — | Python toolkit: AST parser, dataflow analyser, control-flow analyser for Verilog |
| Thakur 2023 — AutoChip | 2311.04887 | Iterative LLM Verilog generation with simulation feedback |
| Blocklove 2023 — Chip-Chat | 2305.13243 | Conversational LLM hardware design exploration |
| Chang 2023 — ChipGPT | 2305.14019 | Natural-language hardware design with LLMs |
| Orenes-Vera 2023 | 2309.09437 | LLMs for formal verification of RTL |
| Zhang 2023 — LLM4DV | 2310.04535 | LLMs for hardware test stimulus generation |

All 9 references verified correct as of session creation.

---

## 13. Files in This Project Folder

| File | Purpose |
|---|---|
| `CLAUDE.md` | **This file** — project context for Claude sessions |
| `PROGRESS.md` | Running progress tracker — update as work proceeds |
| `expose.tex` | Final LaTeX exposé (uses scrreprt template, ready to compile) |
| `LaTeX_expose_template_simple (1).tex` | Professor's original template |
| `project_info.md` | Project metadata (duplicate of section 1 here) |
| `project_description.txt` | Professor's official S6.ReKI.1 description |
| `paper.pdf` | AutoBench paper (already summarized in this file — don't re-read unless asked) |

---

## 14. Tech Stack

- **Language:** Python 3.11+
- **LLM:** provider-agnostic (OpenAI-compatible). Current: OpenRouter — `claude-sonnet-4.5` (strong: code/reasoning) + `gpt-4o-mini` (cheap: classify/scenarios). Groq/Anthropic/OpenAI also supported.
- **Pipeline:** LangGraph (graph-based state machine)
- **Static analysis:** Pyverilog
- **Simulator:** Icarus Verilog (`iverilog`, `vvp`) — IEEE 1800-2012
- **Testing:** pytest + smoke benchmark (5–10 modules)
- **Version control:** Git

---

## 15. Conventions for This Project

- **Pipeline must be graph-based** — every step a LangGraph node; no hidden control flow
- **Prompts go in `prompts/` directory** as Jinja templates, not inline strings
- **All LLM calls logged** — node, model, tokens, latency
- **Temperature configurable** via `LLM_TEMPERATURE` (default 0.7, supervisor's choice; Constitution v1.1.0). **Temp 0.7 only as of 2026-08-24** — the temp-0 arm is dropped; use repeats for error bars instead.
- **CMB before SEQ** — never start sequential work until combinational pipeline is solid
- **Don't re-read `paper.pdf`** unless I ask — section 4 above is the canonical summary
- **Don't run any code or install dependencies** until Phase 1 begins (after dataset arrives)

---

## 16. Open Questions / Unknowns

- ✅ **Scope pivot confirmed** — supervisor email 2026-05-26 confirmed testbench gen + Pyverilog localisation.
- ⚠️ **Dataset re-scoped (2026-08-24)** — the VerilogEval 156 run is **not funded** and will not be done. Evaluation uses a 12-circuit set (6 easy existing + 6 purpose-built hard) × 5 modes × 2 repeats at temp 0.7. Note the absence of a public-benchmark head-to-head as a limitation in the report.
- **Pyverilog robustness on LLM-generated code** — *quantified* (2026-07-15): Pyverilog parses **7/8** LLM testbenches after fixing a concat/newline bug; Verible fallback (now installed) covers the rest. Failure was structural (parse), not semantic.
- ✅ **SEQ standardisation** — done deterministically in Python (`fdisplay_inserter.py`), no LLM.
- **Overfitting / generalisation** — the SEQ prompt was tuned on the 8 local fixtures. Without the 156 held-out run this cannot be fully resolved; mitigate by freezing prompts before the sweep and by adding 6 circuits the prompt was never tuned on.
- **Static checks are untestable on trivial circuits** (2026-08-24) — four of five checks cannot fire on 8–17 line fixtures with 2–4 unambiguous ports: `port_binding_mismatch` needs ≥3 confusable names, `width_mismatch` needs differing bus widths, `undriven_input` needs enough inputs to forget one, `sensitivity_list_error` needs `always` blocks the testbench does not have. Hence the hard-circuit set and the error-injection study.
- **`WIDTH_MISMATCH` is declared but never emitted** — implement it or remove it from the taxonomy before the report claims it.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:
`specs/006-eval-harness/plan.md`
<!-- SPECKIT END -->
