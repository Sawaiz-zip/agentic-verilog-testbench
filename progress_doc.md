S6.ReKI.1 — Research Progress Document
LLM-Driven Verilog Testbench Generation with Pyverilog-Based Early Error Localization

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROJECT INFORMATION

Student        :  Muhammad Sawaiz Naveed
Email          :  muhammad-sawaiz.naveed@tu-ilmenau.de
Supervisors    :  Shengchao | Wen Bing | Wu Jiajun
University     :  Technische Universität Ilmenau
Final Deadline :  September 1, 2026
GitHub Repo    :  https://github.com/Sawaiz-zip/ResearchProject

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROJECT DESCRIPTION

This project builds a graph-based LLM pipeline that automatically generates
Verilog testbenches from natural-language circuit descriptions. The pipeline
uses Pyverilog static analysis to detect errors in generated testbenches before
any simulation runs, then feeds structured error reports back to the LLM for
repair. The pipeline is implemented as a LangGraph state machine with explicit
nodes, conditional edges, and a repair loop.

Reference Paper  :  AutoBench (arXiv:2407.03891) — MLCAD 2024
Dataset          :  VerilogEval (156 HDLBits problems, confirmed by supervisor)
LLM Models       :  Claude Haiku (classification) + Claude Sonnet (code/reasoning)
Static Analysis  :  Pyverilog (AST + dataflow) with Verible as fallback
Simulator        :  Icarus Verilog (Eval0/1/2)
Orchestration    :  LangGraph

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PIPELINE OVERVIEW

  [1] Classify circuit (CMB / SEQ)
       ↓
  [2] Extract structured spec (ports, behaviour, timing)
       ↓
  [3] Generate test scenarios
       ↓
  [4a] Generate Verilog driver    [4b] Generate Python checker  ← parallel
       ↓
  [5] Pyverilog static analysis (no simulation)
       ↓
  [6] LLM error reasoning → structured error report
       ↓
  [7] Deterministic standardizer (insert $fdisplay for SEQ)
       ↓
  [8] Repair loop — if errors found, go back to [4] (max 3 iterations)
       ↓
  [9] Icarus Verilog evaluation (Eval0 / Eval1 / Eval2)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EVALUATION METRICS (following AutoBench)

  Eval0  —  Does the testbench compile? (Icarus Verilog)
  Eval1  —  Does it pass against the correct golden DUT?
  Eval2  —  Does it catch bugs in LLM-generated mutant DUTs?

Additional metrics specific to this project:
  - Error precision / recall (Pyverilog-flagged vs real errors)
  - Per-node failure attribution (which stage fails most)
  - Iterations to pass (repair loop distribution)
  - Tokens per module (LLM cost)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RESEARCH QUESTIONS

  RQ1  —  What categories of functional errors appear most frequently in
           LLM-generated testbenches, and which are detectable without simulation?

  RQ2  —  To what extent can Pyverilog AST and dataflow analysis localize
           testbench errors prior to simulation?

  RQ3  —  Can an LLM informed by Pyverilog results effectively repair
           testbench errors vs using only compiler/simulator feedback?

  RQ4  —  What is the cost-quality tradeoff of static analysis + LLM reasoning
           vs relying solely on compiler/simulator feedback?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PHASE STATUS OVERVIEW
(Last updated 2026-09-23)

  Phase 0  —  Setup              Weeks 1–2    May–Jun 2026    ✅ Done
  Phase 1  —  Generation         Weeks 3–6    Jun 2026        ✅ Done
  Phase 2  —  Pyverilog          Weeks 5–9    Jun 2026        ✅ Done
  Phase 3  —  Repair + SEQ       Weeks 10–13  Jun–Jul 2026    ✅ Done
  Phase 4  —  Evaluation         Weeks 14–16  Jul–Aug 2026    ✅ Done
  Phase 5  —  Writing            Weeks 17–20  Aug–Sep 2026    ✅ Done

  Legend:  ✅ Done  |  🟢 On Track  |  🟡 In Progress  |  🔴 Blocked  |  ⚪ Not Started

  NOTE: The per-phase detail sections further down this document were written in
  June 2026 and were not maintained afterwards. For anything after June, the
  authoritative sources are CLAUDE.md (project context and corrections) and
  docs/research-log.md (dated session log).


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FINAL RESULTS SUMMARY
(All figures re-derived from the 280 raw run records on 2026-09-23
 and verified by a 12-assertion check script — all pass.)

  SCALE
    Four sweeps, 280 runs, 32 distinct circuits, ~$16.50 in API spend.
    12 project fixtures (strong + weak model) + 20 VerilogEval circuits
    (strong + weak model). Temperature 0.7 throughout.

  HEADLINE METRICS
    Eval0  (compiles)          259 / 280   92.5%
    Eval1  (works vs golden)    88 / 280   31.4%
    Eval2  (valid mutants)     415 / 437   95.0%   <- a ceiling; see LIMITATIONS

  COMPILE RATE vs AUTOBENCH
    AutoBench, no standardisation   SEQ 55.5%
    AutoBench, with it (their best) SEQ 97.3%
    Ours, standardiser inert        SEQ 90.7%  (182 of 188 runs it never touched)
    Ours, strong model              SEQ 98.7%
    Ours, pooled both models        SEQ 90.4%

    => At comparable model strength we match or slightly exceed them, on the
       hardest quintile of their benchmark. Pooled we do not, because half our
       runs used a cheap model they never tested.
    => Our standardiser fired on only 6 of 188 sequential runs. The defect class
       AutoBench's script existed to fix has largely disappeared from current
       models — the same technique now has almost nothing to do.

  THE REPAIR LOOP
    Runs that attempted a repair       102 of 280
    Of those, ended up passing          26        (25.5%)

    What triggered each repair iteration, project-wide:
      simulation (ran, wrong answers)   79
      blind retry (the control)         64
      compiler errors                   10
      static analysis (our layer)        1   <-- the central finding

  THE ABLATION  (44 runs per mode, three sweeps containing all five)

      mode             passed  1st-try  attempted  rep->pass  rep->fail
      baseline           12      12         0          0          0
      retry_only         13       0        44         13         31
      compiler_only      15      15         2          0          2
      pyverilog_only      9       9         0          0          0
      hybrid             18      15        21          3         18

    Read "attempted" as "made a second try", NOT "was fixed".
      - retry_only attempted 44 and only 13 worked.
      - Of hybrid's 18 passes, 15 were first-attempt and only 3 were rescued by
        repair. The mechanism is worth ~3 circuits of 44 (6.8 pts), not 13.6.
      - pyverilog_only never repaired, so it ran effectively the same logic as
        baseline — and still finished 3 circuits apart. That is the noise floor.
        hybrid's 5-circuit lead over the control sits against a 3-circuit floor.

    hybrid vs retry_only (the fair test):  p = 0.372 — NOT significant.
    retry_only vs baseline:                p = 1.000 — the bare extra try is
                                           worth nothing, so any real gain must
                                           sit on the diagnosis.

  THE LOCALISER, MEASURED (fault-injection study, 215 injected faults)
    Detection                93%
    Localisation             93%   (right class AND right signal)
    False positives           0    on 14 clean testbenches
    Invisible to compiler+simulator: 33 faults, of which it caught 30

    => The instrument is sound. What it detects has become rare.

  LIMITATIONS WE FOUND AND MEASURED RATHER THAN WAVED AWAY
    1. Eval2's 95% is a ceiling caused by our fixture circuits being too small.
       Proven by swapping one variable at a time: better mutants moved it 1 pt,
       different circuits moved it 44. On AutoBench's published mutants the same
       testbenches score 53.8% (an 8-run probe) / 66.7% (strong sweep).
    2. Parser coverage is a selection effect. Pyverilog could read only 262 of
       434 analyses; the rest fell back to Verible, which runs none of the six
       checks. Readable runs pass Eval1 at 45.6%, unreadable at 6.0%.
    3. Co-generation: the localiser reads the generated design, evaluation uses
       the golden one. Measured — 273 of 280 runs (97.5%) match the golden port
       interface; all 7 that differ are Prob150, which invents a clock. Interface
       only; no equivalence check was run.
    4. The ablation cannot attribute hybrid's margin to static analysis. hybrid
       is the ONLY arm that can act on simulation feedback, which drove 79 of the
       90 informed repairs. There is no simulation_only arm to separate them.
    5. Intermediate testbench versions are not stored, so no per-iteration code
       diff can be reconstructed.

  OPEN ITEM TO RESOLVE FROM THE PAPER
    A missing $fdisplay causes a FUNCTIONAL failure, not a COMPILE failure — so
    it is not obvious how inserting one lifts AutoBench's Eval0 by 42 points.
    Either their standardisation script does more structural normalisation than
    our summary records, or the gain has another cause. "Same technique, opposite
    outcome" only holds if it really is the same technique.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PHASE 0 — SETUP
Weeks 1–2  |  May–Jun 2026  |  Status: 🟢 On Track (17/21 tasks done)

Goal: Literature review, development environment, dataset analysis.

Steps:
  [ ]  1.  Read AutoBench paper (arXiv:2407.03891) in full              ✅ Done
  [ ]  2.  Read VerilogEval paper (arXiv:2309.07544)                    ✅ Done (summarised 2026-06-14)
  [ ]  3.  Read Pyverilog paper (Takamaeda 2015)                        ✅ Done (summarised 2026-06-14)
  [ ]  4.  Complete LangGraph introductory course (Module 1)            🟡 In Progress
  [ ]  5.  Write project constitution + spec + plan + tasks (spec-kit)  ✅ Done (2026-06-14)
  [ ]  6.  Create Python project structure with pyproject.toml          ✅ Done (2026-06-14)
  [ ]  7.  Write shared LLM wrapper (llm.py) with logging + backoff     ✅ Done (2026-06-14)
  [ ]  8.  Define GraphState TypedDict with all pipeline fields          ✅ Done (2026-06-14)
  [ ]  9.  Define PipelineConfig + AblationMode enum                    ✅ Done (2026-06-14)
  [ ]  10. Build LangGraph graph skeleton (all 10 nodes registered)     ✅ Done (2026-06-14)
  [ ]  11. Write all 8 Jinja2 prompt templates in prompts/              ✅ Done (2026-06-14)
  [ ]  12. Write error taxonomy dataclasses (ErrorType, PyverilogReport)✅ Done (2026-06-14)
  [ ]  13. Write all 10 node stub files with phase TODO comments        ✅ Done (2026-06-14)
  [ ]  14. Write eval/ and standardiser/ module stubs                   ✅ Done (2026-06-14)
  [ ]  15. Write scripts: aggregate_results.py, run_smoke.sh, run_eval.sh ✅ Done (2026-06-14)
  [ ]  16. Initialise GitHub repo + push skeleton to main branch         ✅ Done (2026-06-14)
  [ ]  17. Create phase-1-generation branch                             ✅ Done (2026-06-14)
  [ ]  18. Install all dependencies (uv sync, Pyverilog, Icarus Verilog)⚪ Not Started
  [ ]  19. Download and analyse VerilogEval dataset (156 problems)      ⚪ Not Started
  [ ]  20. Smoke-test Pyverilog on 2–3 example Verilog modules          ⚪ Not Started
  [ ]  21. Add 5 CMB fixtures to tests/fixtures/cmb/                    ⚪ Not Started

Deliverable: Working dev environment, Pyverilog confirmed to parse
             VerilogEval-style code, dataset loaded and inspected.

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
Supervisor Comments (Phase 0):



- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PHASE 1 — TESTBENCH GENERATION (COMBINATIONAL)
Weeks 3–6  |  Jun 2026  |  Status: 🟡 In Progress (skeleton complete, implementation next)

Goal: Build the LangGraph pipeline skeleton and generate working testbenches
      for combinational (CMB) circuits. Eval0 and Eval1 passing.

Note: GraphState, LLM wrapper, graph skeleton, and all 8 prompts were completed
      in Phase 0 (2026-06-14). Remaining work is filling in the node implementations.

Steps:
  [ ]  1.  GraphState TypedDict with all fields                          ✅ Done (Phase 0)
  [ ]  2.  All 8 Jinja2 prompt templates in prompts/                    ✅ Done (Phase 0)
  [ ]  3.  LangGraph graph skeleton with all nodes registered            ✅ Done (Phase 0)
  [ ]  4.  Implement classify_node — CMB vs SEQ (Haiku)                 ⚪ Not Started
  [ ]  5.  Implement extract_spec_node — JSON spec (Sonnet)             ⚪ Not Started
  [ ]  6.  Implement gen_scenarios_node — scenario list (Haiku)         ⚪ Not Started
  [ ]  7.  Implement gen_driver_node — Verilog testbench (Sonnet)       ⚪ Not Started
  [ ]  8.  Implement gen_checker_node — Python checker (Sonnet)         ⚪ Not Started
  [ ]  9.  Wire gen_driver + gen_checker as parallel LangGraph branches  ⚪ Not Started
  [ ]  10. Implement icarus.compile_tb() — Eval0 subprocess wrapper     ⚪ Not Started
  [ ]  11. Implement icarus.simulate_tb() — Eval1 subprocess wrapper    ⚪ Not Started
  [ ]  12. Implement icarus.eval2() — run TB against mutant DUTs        ⚪ Not Started
  [ ]  13. Implement mutant_gen.generate_mutants() — Haiku fault inject ⚪ Not Started
  [ ]  14. Implement evaluate_node — orchestrate Eval0/1/2 + results    ⚪ Not Started
  [ ]  15. Smoke test on 5 CMB fixtures (gate: Eval0 ≥ 80%, Eval1 ≥ 50%)⚪ Not Started

Deliverable: Pipeline generates a compilable, functionally correct testbench
             for simple CMB circuits (AND gate, mux, adder) end-to-end.

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
Supervisor Comments (Phase 1):



- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PHASE 2 — PYVERILOG STATIC ANALYSIS
Weeks 5–9  |  June 2026  |  Status: ⚪ Not Started

Goal: Build the Pyverilog analysis layer that catches testbench errors
      before simulation and feeds structured reports to the LLM.

Steps:
  [ ]  1.  Build PyverilogNode — parse testbench + golden DUT together
  [ ]  2.  AST checks: port bindings (TB ↔ DUT), sensitivity lists
  [ ]  3.  Dataflow checks: undriven inputs, unobserved outputs, width mismatches
  [ ]  4.  Presence checks: $fdisplay for every output (SEQ circuits)
  [ ]  5.  Add Verible fallback when Pyverilog rejects LLM-generated syntax
  [ ]  6.  Define structured error report format:
               {error_type, affected_signal, line, suggested_fix, severity}
  [ ]  7.  Implement ErrorReasonNode (Sonnet) — translate Pyverilog report
               into LLM-readable error explanations
  [ ]  8.  Build error taxonomy: categorise error types, tag each as
               Pyverilog-detectable or simulation-only
  [ ]  9.  Hand-label 20 dev-set modules to measure Pyverilog precision/recall
  [ ]  10. Write reusable pyverilog_analyzer.py module (importable, tested)

Deliverable: Pyverilog module correctly identifies port binding errors,
             sensitivity list bugs, and missing $fdisplay on a labelled dev set.
             Error taxonomy document with frequency and detectability.

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
Supervisor Comments (Phase 2):



- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PHASE 3 — REPAIR LOOP + SEQUENTIAL CIRCUITS
Weeks 10–13  |  June–July 2026  |  Status: ⚪ Not Started

Goal: Close the feedback loop so the LLM can repair errors using Pyverilog
      guidance. Extend the pipeline to handle sequential (SEQ) circuits.

Steps:
  [ ]  1.  Implement repair loop as a conditional LangGraph edge
  [ ]  2.  RepairRouter node — decision logic:
               (a) no errors → proceed to evaluation
               (b) same errors as last iteration → oscillation detected → stop
               (c) repair_iter >= 3 → exhausted → stop
               (d) errors found + iter < 3 → feed back to DriverGenNode
  [ ]  3.  Implement oscillation detection (compare error_report to last)
  [ ]  4.  Implement DeterministicStandardizerNode (Python AST, no LLM):
               insert missing $fdisplay, normalise clock sensitivity lists
  [ ]  5.  Extend DriverGenNode to accept error_report context on repair iters
  [ ]  6.  Add SEQ circuit support throughout the pipeline
  [ ]  7.  Implement Eval2 — run testbench against LLM-generated mutant DUTs,
               measure fraction of mutants caught
  [ ]  8.  Full end-to-end test on 20 CMB + 10 SEQ modules
  [ ]  9.  Confirm repair loop reduces Eval0/1/2 failure rate vs no-repair baseline

Deliverable: Complete pipeline running end-to-end for both CMB and SEQ circuits
             with repair loop active. Eval0/1/2 results logged per module.

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
Supervisor Comments (Phase 3):



- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PHASE 4 — EVALUATION + ABLATIONS
Weeks 14–16  |  July–August 2026  |  Status: ⚪ Not Started

Goal: Run full evaluation on the held-out test set (80% of VerilogEval).
      Compare ablation conditions to quantify each component's contribution.

Steps:
  [ ]  1.  Freeze all prompts before running the test set (no further tuning)
  [ ]  2.  Run full pipeline on held-out test set (125 modules)
  [ ]  3.  Run 4 ablation conditions on the same test set:
               (a) Baseline — no repair, no static analysis
               (b) Compiler-feedback only — repair using iverilog errors only
               (c) Pyverilog-only — static analysis, no LLM error reasoning
               (d) Hybrid (ours) — Pyverilog + LLM error reasoning + repair loop
  [ ]  4.  Collect per-node failure attribution from LangGraph telemetry
  [ ]  5.  Collect iterations-to-pass distribution
  [ ]  6.  Collect token cost per module for each condition
  [ ]  7.  Analyse Pyverilog error precision and recall vs hand-labelled ground truth
  [ ]  8.  Compare Eval0/1/2 results across all 4 conditions
  [ ]  9.  Identify most common failure modes and document them
  [ ]  10. Prepare results tables and figures for the final report

Deliverable: Full evaluation results across 4 ablation conditions.
             All metrics collected: Eval0/1/2, precision/recall,
             iterations, tokens, failure attribution.

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
Supervisor Comments (Phase 4):



- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PHASE 5 — FINAL REPORT
Weeks 17–20  |  August–September 2026  |  Status: ⚪ Not Started

Goal: Write and submit the final research report by September 1, 2026.

Steps:
  [ ]  1.  Write Introduction (motivation, problem statement, contributions)
  [ ]  2.  Write Related Work (AutoBench, VerilogEval, Pyverilog, LLM4DV)
  [ ]  3.  Write Methodology (pipeline architecture, each node, design decisions)
  [ ]  4.  Write Evaluation Setup (dataset split, metrics, ablation design)
  [ ]  5.  Write Results (tables, figures, answer each RQ explicitly)
  [ ]  6.  Write Discussion (failure analysis, limitations, future work)
  [ ]  7.  Write Conclusion
  [ ]  8.  Proofread + supervisor review round
  [ ]  9.  Final submission by September 1, 2026

Deliverable: Submitted final report.

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
Supervisor Comments (Phase 5):



- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WEEKLY LOG
(Most recent week first)

────────────────────────────────────────
Week of 22 September 2026
────────────────────────────────────────
Completed:
  - Re-derived every headline figure directly from the 280 raw run records and
    verified them with a 12-assertion check script (all pass). Several had never
    been written down; two corrected a misreading of the results tables.
  - Measured, for the first time, how far the pipeline's own generated design
    diverges from the golden reference: 273 of 280 runs (97.5%) match on port
    interface; all 7 that differ are Prob150, which invents a clock. This
    localises the co-generation threat from "general concern" to one circuit.
  - Established that AutoBench's standardisation gain has genuinely expired
    rather than merely being unused: our standardiser fired on 6 of 188
    sequential runs, and the 182 it never touched still compile at 90.7% against
    AutoBench's un-standardised 55.5%.
  - Found a real gap in our own ablation design: hybrid is the only arm that can
    act on simulation feedback (79 of 90 informed repairs), so its margin cannot
    be attributed to the static layer. No simulation_only arm exists to separate
    them. Now documented rather than left for an examiner.
  - Built scripts/show_run.py — extracts any run's Verilog artefacts as real
    files for inspection and diffing (--list, <run_id>, --circuit, --compare).
    Its per-iteration static-analysis table makes the Prob150 repair story
    legible in four rows.
  - Published the human-readable results: results/RESULTS.md indexing all four
    sweeps, plus the previously missing verilogeval_strong/REPORT.md. Fixed
    .gitignore so these are tracked while the 690 per-run JSONs stay local.
  - Rewrote the learning series for a non-specialist reader, with an AutoBench
    comparison at every pipeline node and a "did it help?" verdict carrying the
    real number.

Open / next:
  - Verify from the AutoBench paper how their standardisation script lifts Eval0
    by 42 points, given that a missing $fdisplay breaks behaviour rather than
    compilation.
  - Backfill this log for 2026-08-29 to 2026-09-01 (fourth sweep, co-generation
    re-analysis, mutant-quality pilot, report build) — recorded in CLAUDE.md but
    never logged here.

────────────────────────────────────────
Week of 14 June 2026
────────────────────────────────────────
Completed:
  - Summarised all 3 core papers (AutoBench, VerilogEval, Pyverilog) in plain English
  - Installed spec-kit (specify-cli v0.10.2) and ran full SDD planning workflow
  - Wrote project constitution (10 engineering principles)
  - Wrote feature spec with 5 user stories, 13 FRs, 7 success criteria
  - Wrote implementation plan with full file tree and 6-phase breakdown
  - Wrote 59-task task list with phase markers and parallel flags
  - Built complete Python project skeleton (81 files committed):
      · pipeline/ package: state, config, llm wrapper, graph, 10 node stubs
      · analysis/ module: error taxonomy dataclasses, pyverilog + verible stubs
      · standardiser/ module: fdisplay inserter stub
      · eval/ module: icarus wrapper stub, mutant generator stub
      · prompts/: all 8 Jinja2 templates written and ready
      · tests/: pytest harness + 2 passing unit tests
      · scripts/: run_smoke.sh, run_eval.sh, aggregate_results.py
  - Pushed skeleton to GitHub (https://github.com/Sawaiz-zip/ResearchProject)
  - Created phase-1-generation branch — ready to start implementation

In Progress:
  - LangGraph introductory course (Module 1)

Next Week:
  - Install dependencies (uv sync + iverilog + pyverilog smoke test)
  - Download VerilogEval dataset + add 5 CMB fixtures
  - Implement Phase 1 nodes on phase-1-generation branch (classify → evaluate)

Comments from supervisors:


────────────────────────────────────────
Week of 26 May 2026
────────────────────────────────────────
Completed:
  - Received supervisor confirmation on scope, dataset, and evaluation metrics
  - Pipeline architecture designed (LangGraph nodes, repair loop, parallel branches)
  - Sequence diagram and component UML diagram created
  - Project GitHub repo initialised
  - Google Doc created and shared with supervisors

In Progress:
  - LangGraph introductory course (Module 1)

Next Week:
  - Finish LangGraph course
  - Set up Python project structure
  - Install and smoke-test Pyverilog

Comments from supervisors:



━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OPEN QUESTIONS FOR SUPERVISORS
(Clear each question once answered)

  1.  [ANSWERED] Is Pyverilog static analysis the right approach?
      → Yes, confirmed by Shengchao (26 May 2026)

  2.  [ANSWERED] Is VerilogEval sufficient as the dataset?
      → Yes, confirmed by Shengchao (26 May 2026)

  3.  [ANSWERED] Should we use golden models from VerilogEval for evaluation?
      → Yes, follow AutoBench Eval0/1/2 metrics (26 May 2026)

  4.  (Add new questions here as they arise)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

KEY DECISIONS LOG

  2026-05-10  Adopted LangGraph for orchestration — explicit graph with
              conditional edges and feedback loops as first-class constructs.

  2026-05-10  Chose Claude API (Haiku + Sonnet) — Haiku for cheap
              classification nodes, Sonnet for code generation and reasoning.

  2026-05-10  CMB circuits before SEQ — AutoBench achieved only 26% Eval2
              on SEQ; we de-risk by getting CMB solid first.

  2026-05-20  Replaced AutoBench's LLM-based $fdisplay insertion with a
              deterministic Python AST pass — LLM behaviour is fragile
              on a mechanical formatting task.

  2026-05-20  Added Verible as a fallback parser in case Pyverilog cannot
              handle LLM-generated Verilog syntax edge cases.

  2026-05-20  Repair loop gets oscillation detection — if the same error
              report appears twice in a row, break the loop immediately.

  2026-05-26  VerilogEval confirmed as dataset by supervisor — 80/20
              dev/test split, prompts frozen before running the test set.

  2026-06-14  Installed spec-kit (specify-cli v0.10.2) and wrote full
              planning docs (constitution, spec, plan, 59 tasks) before
              any implementation — ensures every node has a spec and RQ mapping.

  2026-06-14  All 8 prompt templates written as Jinja2 before implementing
              nodes — prevents inline prompt strings from slipping into code.

  2026-06-14  Shared LLM wrapper (llm.py) written first — all nodes call
              this single function to guarantee logging and temperature=0
              without repeating boilerplate in each node.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
