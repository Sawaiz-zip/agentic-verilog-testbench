# Project Context — S6.ReKI.1

> **For future Claude sessions:** This file is the single source of truth for this research project.
> Read it first. Then check `docs/research-log.md` for current status.
> Do not re-derive anything from `paper.pdf` unless explicitly asked — the summary below is authoritative.

---

## 1. Project Metadata

| Field | Value |
|---|---|
| **Topic ID** | S6.ReKI.1 |
| **Title** | LLM-Driven Verilog Testbench Generation with Pyverilog-Based Early Error Localization |
| **Student** | Muhammad Sawaiz Naveed |
| **Student email** | muhammad-sawaiz.naveed@tu-ilmenau.de |
| **Supervisor** | Bing Wen |
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

> **Status as of 2026-08-29** — full evidence in `docs/results.md`; corrections this date in git log.
> **RQ1 ✅ answered:** 87% of failures are semantic (133 of 153). ⚠️ **Bounded 2026-08-29:** re-simulating all 133 against their *own generated* DUT gives 108 confirmed testbench-internal (81%), 3 faithful-TB-wrong-DUT (2%), 22 indeterminate (generated DUT won't elaborate). Read as "108 confirmed, 25 unresolved". Uncategorised scenarios are **209**, not 206.
> **RQ2 ✅ answered, both halves.** ⚠️ **Denominator corrected 2026-08-29:** Pyverilog parsed only **190 of 314** analyses; 120 fell back to Verible (syntax-only — *no structural check ran*, recorded as `parse_ok`). Quote **2 findings in 190**, never 2 in 314. Worst on the benchmark sweep (64/153). Detection side unchanged: 93% of 215 injected faults, 0 false positives, 30 of 33 invisible to compiler+simulator.
> **RQ3 ⚠️ partially.** The "informed by Pyverilog" half is unanswerable — almost no findings to inform it. Comparison half: hybrid vs `retry_only` gap is **11.4 points** (NOT 17 — old error), p=0.372 unpaired / **p=0.125 McNemar paired**. Arms are circuit-matched so paired tests apply; hybrid vs `pyverilog_only` reaches p=0.012 paired but fails Bonferroni and is uninformative (pyverilog_only never repaired). **Decomposition:** hybrid's 18 passes = 15 first-attempt (baseline 12, same process → noise) + **3 rescued by repair**; the mechanism is worth 6.8 points, not 13.6.
> **RQ4 ✅ answered:** `hybrid` buys +13.6 points Eval1 for +50% tokens; `compiler_only` is the efficiency winner (+7 points for +6%); `pyverilog_only` costs ~nothing and gains nothing.

### Findings added 2026-08-29 (not in the original four RQs)

- **Why repairs fail.** 23 runs performed a diagnosed repair; **3 passed (13%)**. Of the 20 failures: 7 regenerated a testbench failing the *identical* scenario set (diagnosis not acted on); 13 exhausted the budget with a *different* error signature every iteration — across 14 multi-iteration runs **no signature ever repeated**. Ten of seventeen ended 1–2 scenarios short. Prior work does not report this.
- **Eval2 ceiling is a fixture-size artefact, not a mutant artefact.** Pre-registered pilot (`specs/012-mutant-quality/PILOT_CRITERIA.md`, committed before generation): regenerating mutants with the strong model under AutoBench's own prompt, equivalent mutants filtered, gives **97.4%** vs 96.7% before — one point. The same testbenches score **53.8%** on AutoBench's *published* mutants for the benchmark circuits. Prompt structure governs diversity; model governs validity; neither governs the score. Correct pooled Eval2 is **324/335**, not 189/190 (that was one sweep).
- **AutoBench's mutants are public** — `AutoBench/AutoBench` on GitHub, `data/HDLBits/HDLBits_data_mutants.jsonl`, 1,525 mutants covering all 156 problems (20/20 of our benchmark subset). Their Eval2 is *agreement with the golden TB at ≥80%*, not raw detection; under their rule our benchmark runs give 10%.
- **AutoBench's Eval1 figures** (from paper Table 1, never previously cited here): **51.47% total, 64.81% CMB, 37.07% SEQ**; Eval0 95.71%; Eval2 44.81%.
- ⚠️ **The 20-problem benchmark subset is the hardest quintile** (complexity 26.4–41.9 vs median 18.7; 75% sequential vs the benchmark's 48%) **and was run with the cheap model**. No relative standing vs AutoBench is established. Weighting their numbers to a 75%-SEQ mix gives ~44%, not 51.47%.
- **Variance floor is sample-size dependent.** 33 points is at n=12/arm (expected spread of 3 identical arms there is ~24, so 33 is a high-but-ordinary draw). At n=44 it is ~12 expected, and the *measured* null gap between `baseline` and `pyverilog_only` (identical logic) is **6.8 points**. Judge the 11.4-point gap against 6.8, not 33.


- **RQ1.** What categories of functional errors appear most frequently in LLM-generated Verilog **testbenches**, and which of these are detectable without full simulation?
- **RQ2.** To what extent can Pyverilog's AST and dataflow analysis (port bindings, sensitivity lists, dataflow consistency between testbench and DUT) narrow down testbench errors prior to simulation?
- **RQ3.** Can an LLM, informed by Pyverilog analysis results, effectively localise and repair testbench errors, and how does this compare to using only compiler/simulator feedback as in prior work?
- **RQ4.** What is the cost–quality tradeoff of combining lightweight static analysis with LLM reasoning vs relying solely on compiler/simulator feedback for repair?

---

## 9. Expected Contributions

1. **LangGraph testbench-generation pipeline** — open-source, modular, graph-based workflow with explicit nodes for classification, spec extraction, scenario generation, driver/checker generation, static analysis, error reasoning, standardisation, repair, and evaluation. This is the primary contribution and matches the project description's focus on graph-based LLM workflows.
2. **Pyverilog-based pre-simulation error localiser** — reusable Python module converting Pyverilog AST/dataflow output into structured, LLM-readable summaries focused on testbench-DUT interaction errors.
3. **Deterministic `$fdisplay` standardiser** — Python AST pass that replaces AutoBench's fragile LLM-based standardisation step.
4. **Testbench-error taxonomy with measured detectability** — six error classes, each verified by fault injection: 215 injected faults across 14 testbenches, scored against static analysis, the compiler, and the simulator. Includes a negative result (one check removed for zero recall) and an explicit boundary (semantic faults such as swapped same-width bindings are undetectable statically).
5. **Per-run failure *detection* attribution and full execution telemetry** — every run records the stage at which failure was detected, the feedback source that triggered each repair, and per-call model/token/latency data. ⚠️ **Scope corrected 2026-08-25:** the original wording claimed attribution of where failures *originate* across the 6 stages. The data does not support that: 70% of runs attribute to `evaluate` and 30% to `none`, because `evaluate` is where failure is *detected*, not where the defect was introduced. Origin attribution would require per-node ground truth the pipeline does not collect. What is delivered — and what AutoBench does not provide — is the repair-feedback breakdown (25 simulation, 8 compile, 0 static across 220 runs) and the cost telemetry behind RQ4.
6. **Empirical comparison of feedback strategies** — baseline, retry-only (control), compiler-only, Pyverilog-only, and hybrid, across CMB and SEQ benchmarks. The `retry_only` arm is what makes the comparison sound: every repairing mode gets an extra LLM sample that baseline does not, so without it a gain cannot be attributed to the feedback.

---

## 10. Evaluation Metrics

| Metric | Description |
|---|---|
| **Eval0** | Testbench compilation pass rate (Icarus Verilog) |
| **Eval1** | Testbench passes against golden DUT |
| **Eval2** | Testbench distinguishes golden DUT from LLM-generated mutants |
| **Error precision** | Pyverilog-flagged errors that are real — **measured 2026-08-24: 0 false positives on 14 clean testbenches (100%)** |
| **Error recall** | Real errors that Pyverilog catches — **measured: 93% over 215 injected faults; 93% localised to the right class *and* signal** |
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
| `docs/research-log.md` | Running progress tracker — update as work proceeds |
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
  - **Reopened 2026-08-29.** Measured per-run cost from telemetry is far below the earlier estimate: `baseline` \$0.074, `retry_only` \$0.108, `hybrid` \$0.103 per run at the strong tier. Full 156 × 3 modes ≈ \$44 / 19.5 h; **random 60 × 3 modes ≈ \$17 / 7.5 h**. A strong-model sweep on the existing hard-20 (`results/verilogeval_strong`, baseline + hybrid) was run this date.
  - ⚠️ **Design constraint for any further benchmark run: it MUST include `retry_only`.** A baseline-vs-hybrid comparison without the control reproduces exactly the confound this project criticises AutoBench for (Contribution #4, report §2.6). Prefer a *random* sample with 3 arms over the full 156 with 2 arms — the current 20 are the hardest quintile and are not representative.
- **Pyverilog robustness on LLM-generated code** — *quantified* (2026-07-15): Pyverilog parses **7/8** LLM testbenches after fixing a concat/newline bug; Verible fallback (now installed) covers the rest. Failure was structural (parse), not semantic.
- ✅ **SEQ standardisation** — done deterministically in Python (`fdisplay_inserter.py`), no LLM.
- **Overfitting / generalisation** — the SEQ prompt was tuned on the 8 local fixtures. Without the 156 held-out run this cannot be fully resolved; mitigate by freezing prompts before the sweep and by adding 6 circuits the prompt was never tuned on.
- ✅ **Static checks now testable** (2026-08-24) — the original fixtures could not exercise them: four of five checks cannot fire on 8–17 line circuits with 2–4 unambiguous ports (`port_binding_mismatch` needs ≥3 confusable names, `width_mismatch` needs differing bus widths, `undriven_input` needs enough inputs to forget one, `sensitivity_list_error` needs `always` blocks the testbench does not have). Six purpose-built hard fixtures fixed this; **six of seven checks are now injection-verified**. Day 3 turns the spot check into precision/recall figures.
- ✅ **RQ2 answered empirically** (2026-08-24) — error-injection study over 14 testbenches and 215 injected faults: static analysis 93% detection / 93% localisation / 0 false positives. **33 of 215 faults (15%) are invisible to both the compiler and the simulator; static analysis catches 30 of them (91%).** The decisive class is `unobserved_output` (19 faults, static 100%, compiler 0%, simulator 0%): a testbench that stops checking an output *passes*, because it is no longer looking. Raw data `results/injection_study_final.json`, write-up `specs/011-error-injection-study/NOTES.md`.
- ⛔ **`SENSITIVITY_LIST_ERROR` removed** (2026-08-24) — negative result: 0/5 recall on the fault it existed to catch, plus a false positive on a passing testbench. It inspected `always` blocks inside the testbench, but LLM testbenches drive from `initial` blocks. `CLOCK_NEVER_TOGGLED` covers the concern at 6/6. **Six checks remain, all injection-verified.**
- ✅ **`WIDTH_MISMATCH` implemented** (2026-08-24) — was declared in the taxonomy and emitted nowhere; now compares DUT port widths against the bound testbench signals. A guard test fails if any taxonomy member has no emitting code path. `CLOCK_NEVER_TOGGLED` added alongside it: a clock assigned once and never toggled was invisible to every existing check.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:
`specs/006-eval-harness/plan.md`
<!-- SPECKIT END -->
