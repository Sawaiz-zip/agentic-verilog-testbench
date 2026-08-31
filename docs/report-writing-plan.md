# Report Writing Plan — S6.ReKI.1

Companion to `report-outline.md`. That document fixes *what* the report says; this one
fixes *how and in what order it gets written*, and the rules the prose must follow.

Target: **≤ 40 pages total** (body ≈ 34–36 pp plus front matter and references),
`scrreprt` matching `expose.tex`. Output file: `report.tex`.

**Chapter count reduced from 11 to 9** to meet the page budget. Background and Related Work
are merged; Threats to Validity becomes a section of Discussion rather than its own chapter.
Nothing is dropped — the compression falls on background material, per Part E.

---

## Part A — House style

The report must read as though one engineer wrote it while doing the work, because that is
what happened. The single strongest defence against prose that reads as machine-generated
is **specificity**: this project has commit hashes, exact counts, real error messages, dated
corrections and a removed check. Use them.

### Rules

1. **Prefer the concrete number to the adjective.** Not "detection was very high" — "93%
   of 215 injected faults". Never "significantly", "substantially", "notably", "crucially".
2. **No paragraph-opening connectives.** Ban *Furthermore, Moreover, Additionally, In
   addition, Notably, Importantly*. If two paragraphs need a link, restate the subject.
3. **Do not summarise the paragraph you just wrote.** Cut any final sentence that begins
   "This demonstrates that…", "Thus it can be seen…", "This highlights…".
4. **Vary paragraph length deliberately.** A two-sentence paragraph after a long one reads
   as a person thinking. Uniform 5-sentence blocks read as a template.
5. **Break the rule of three.** Lists of exactly three parallel items, repeatedly, are the
   clearest tell. Use two. Use five. Use prose.
6. **State judgements and own them.** "We dropped this check because it caught none of the
   five faults it existed for" — not "the check was found to exhibit limited efficacy".
7. **Report what went wrong.** The false-positive bugs, the retracted conclusions, the
   removed check. Examiners trust a report that admits error; detectors do not generate it.
8. **Use domain shorthand naturally.** Write `$fdisplay`, `posedge`, DUT, TB without
   re-explaining after first definition.
9. **Sentences may start with "But" or "So", sparingly.** Perfect formality reads synthetic.
10. **Passive voice only where the actor is genuinely irrelevant.** "The sweep was run"
    is fine; "it was decided that" is not — say who decided and why.
11. **Em-dashes: at most one per page.** Prefer commas, colons, or a full stop.
12. **First person plural ("we") for choices, impersonal for results.** Consistent
    throughout; do not switch register between chapters.

### Self-check before any chapter is considered done
- Does any paragraph open with a banned connective?
- Are there three consecutive paragraphs of similar length?
- Could a specific number replace a vague adjective anywhere?
- Is there at least one concrete detail only the author would know?

---

## Part B — Writing phases

Chapters are **not** written in reading order. Method first (most concrete, builds
momentum), Introduction and Conclusion last (they can only be written once the argument
has settled).

### Phase 0 — Scaffold  *(mechanical, no prose)*
- `report.tex` preamble copied from `expose.tex`; add `booktabs`, `longtable`, `siunitx`,
  `caption`, `subcaption`, `float`, `microtype`
- Title block, declaration, abstract placeholder, `\tableofcontents`
- All 11 `\chapter` and `\section` stubs with `\label{}`s
- Bibliography carried over (9 entries), plus new: Verible, LangGraph, Icarus, Wilson score
- **Gate:** compiles to a PDF with an empty but correctly numbered structure

### Phase 1 — System Design and the Localiser  *(Ch. 3, 4 — ~9.5 pp)*
Written first: these are the parts with the most concrete material.
- 4.1–4.7 pipeline, standardiser, repair loop, harness, engineering practices
- 5.1–5.5 the six checks, the removed check, the false-positive history
- Figures: graph topology (from `diagrams/`), a structural-vs-semantic code listing
- **Gate:** a reader could re-implement the pipeline from Chapter 4 alone

### Phase 2 — Instrument Validation and Experimental Design  *(Ch. 5, 6 — ~7 pp)*
- 6.1–6.7 fault injection: why, method, safeguards, the three-layer table
- 7.1–7.6 sweeps, circuit selection, the five arms, prompt freezing, statistics
- **Gate:** §7.2 makes clear the VerilogEval 20 were chosen before running, and why that
  matters for validity

### Phase 3 — Results  *(Ch. 7 — ~6.5 pp)*
- Tables generated from `scripts/analyse_results.py` output, not retyped
- Every number cross-checked against `docs/results.md`
- **Gate:** no claim in the chapter lacks a table, figure or test statistic

### Phase 4 — Discussion, including Threats  *(Ch. 8 — ~5.5 pp)*
- 9.1 the refutation of each alternative explanation — the chapter that carries the report
- 9.3 the AutoBench "same technique, different era" argument
- 10 threats, including the corrections made during development
- **Gate:** every objection an examiner could raise in §9.1 is answered with data

### Phase 5 — Background and Related Work  *(Ch. 2, merged — ~5.5 pp)*
Written after the results so the framing matches what was actually found.
- 2.2 structural vs semantic, with the code example
- 3.1 AutoBench in detail, including its missing control arm
- **Gate:** §3.4 gap statement matches the contributions claimed in Ch. 1

### Phase 6 — Introduction and Conclusion  *(Ch. 1, 9 — ~5 pp)*
Written last, when the argument is fixed.
- 1.5 states the negative result plainly
- 11 the four movements from `report-outline.md`
- Abstract written after the conclusion
- **Gate:** abstract, §1.5 and Ch. 11 agree on the headline numbers

### Phase 7 — Consistency and polish
- Every number appears identically everywhere (script-assisted check)
- Cross-references resolve; no `??`
- Figure and table captions self-contained
- Style self-check applied per chapter
- **Gate:** clean compile, no overfull boxes over 5pt

---

## Part C — Point sequence per section

Each entry is the order of argument, not a summary. One paragraph per bullet unless noted.

### Ch. 1 Introduction
1. Verification consumes 49% of design engineer time; testbench writing is manual and slow
2. LLMs can draft a testbench in seconds — but the failure mode is silent: valid syntax,
   wrong behaviour, and a testbench that reports success having tested nothing
3. The obvious remedy is to simulate and inspect, which costs a full cycle per attempt
4. **The hypothesis:** some faults are visible by reading the code, so a static pass could
   localise them before simulation. Prior work supports the premise — AutoBench's largest
   single gain came from a mechanical pre-simulation fix
5. RQ1–RQ4, stated as questions
6. **What was found**, plainly: the localiser works (93%, 0 FP, 30 faults invisible to
   compiler and simulator) and it fired twice in 314 analyses of real output
7. Five contributions, with #5 at its corrected scope
8. Roadmap paragraph

### Ch. 2 Background
1. Simulation-based verification; where the testbench sits
2. **Structural vs semantic faults** — definition, then the two code listings side by side.
   Structural: a 4-bit signal on an 8-bit port. Semantic: `if (count === 4'd1)` where the
   correct value is `4'd0`. Reading finds the first; only running finds the second
3. What LLMs are good and bad at in HDL, with the pattern-following argument foreshadowed
4. Pyverilog: AST, dataflow, and its known fragility on generated code; Verible fallback
5. Eval0/1/2 defined once, used everywhere after

### Ch. 3 Related Work
1. AutoBench: pipeline, then the three self-enhancement mechanisms in detail
2. AutoBench results: Eval0 95.7%, Eval2 44.8% / CMB 62.2% / SEQ 26.0%; note the SEQ
   Eval0 55.47% → 97.33% from the standardisation script
3. Two observations that matter later: nothing in AutoBench parses Verilog, and its
   ablation has no control arm, so +8% and +10% cannot separate feedback from retry
4. VerilogEval as dataset; AutoChip, ChipGPT, Chip-Chat, LLM4DV briefly
5. Mutation testing as an evaluation method, and its dependence on mutant difficulty
6. Gap statement

### Ch. 4 System Design
1. Why a graph: explicit state and edges, inspectable control flow, per-node telemetry
2. Topology figure; the typed state and its reducers
3. Generation stages in order, one short paragraph each
4. Parallel driver/checker branches and the fan-in barrier
5. The deterministic standardiser: what it inserts, idempotency, fail-safe behaviour, and
   why a Python pass rather than an LLM
6. The repair loop: three feedback sources, the iteration bound, oscillation detection,
   best-so-far retention and the bug that motivated it
7. Evaluation harness: budget guard, rate-limit and out-of-credit aborts
8. Practices: frozen prompts, telemetry, a test suite that spends no tokens

### Ch. 5 The Static Localiser
1. Design principle: detect only what reading can establish; anything needing the
   reference behaviour is out of scope by construction
2. The six checks, one paragraph each, each ending with whether compiler or simulator
   could have found it
3. `width_mismatch` gets extra space: Verilog truncates silently, `iverilog` exits 0 with
   a warning — quote the actual warning text
4. **The removed check.** `sensitivity_list_error`: what it looked for, why it was wrong
   (it inspected `always` blocks inside the testbench, but generated testbenches drive from
   `initial` blocks), the 0/5 recall, the false positive, and the decision to drop it
5. **False positives as the primary risk.** Four found during development. The
   string-literal defect in detail: `$display("PASS: addition_boundary_overflow")` made the
   `overflow` output appear observed. Detection for that class moved 47% → 100% once fixed
6. Parse robustness figures

### Ch. 6 Instrument Validation
1. The problem: end-to-end pass rates cannot say which faults the analyser *could* have
   caught, only whether a run passed
2. Method: known-good testbench, one injected fault, three layers asked the same question
3. The eight injectors; the two negative controls and why a deliberately undetectable
   fault belongs in the study
4. Three safeguards, each with the failure it prevents: mutations must be legal Verilog;
   the corpus is re-verified before injection; golden DUTs rather than generated ones
5. Results table; detection, localisation, false positives
6. `unobserved_output` in its own subsection — the class where static analysis is the only
   detector, and why the simulator cannot see it by construction
7. Boundaries stated without softening

### Ch. 7 Experimental Design
1. Three sweeps and what each isolates
2. Circuit sets; the 12 project fixtures and their easy/hard split
3. **VerilogEval selection**: the complexity criterion, applied before running, with the
   scores; then the explicit argument that selecting on outcomes would void the result and
   that biasing toward the method's best case strengthens a null finding
4. The five arms in a table
5. `retry_only`: the confound it removes, stated concretely
6. Prompt freezing and the tag
7. Statistics: Wilson intervals, Fisher exact, and why not chi-square at these cell counts

### Ch. 8 Results
1. Pipeline reliability first — 220/220, zero harness errors — so later numbers are trusted
2. RQ1: the structural/semantic split, then the category table
3. RQ2a: injection results
4. RQ2b: practical yield, the 2/314 table across sweeps, and `pyverilog_only` never repairing
5. RQ3: the mode table with intervals, then the Fisher matrix, then the plain statement
   that nothing reaches significance
6. The variance floor as its own section with both sweeps' figures
7. `retry_only` degrading Eval0
8. RQ4: cost against quality
9. Cross-model and cross-benchmark consistency

### Ch. 9 Discussion
1. Opening: a null result is only worth reading if the obvious explanations are excluded
2. Four objections, one subsection each, each answered with a specific measurement
3. Why LLMs get structure right and behaviour wrong
4. The AutoBench comparison: same technique, different model generation, opposite outcome
5. Where static analysis would still pay — smaller and local models, and how to test that
6. On measurement practice: single-run pass@1 at this variance
7. Practical recommendation

### Ch. 10 Threats to Validity
Construct, internal, external, statistical — then a short section on corrections made
during the work, written plainly.

### Ch. 11 Conclusion
The four movements from `report-outline.md`, then future work.

---

## Part D — Figures and tables

| # | Item | Chapter | Source |
|---|---|---|---|
| F1 | Pipeline graph topology | 4.2 | `diagrams/` |
| F2 | Structural vs semantic code listing | 2.2 | hand-written |
| F3 | Repair loop state machine | 4.6 | new |
| F4 | Eval1 by mode with CI error bars | 8.5 | `analyse_results.py` |
| F5 | Variance floor illustration | 8.6 | new |
| T1 | The six checks vs compiler/simulator | 5.2 | `docs/results.md` |
| T2 | Fault injection, three layers | 6.5 | injection study |
| T3 | Static findings per sweep | 8.4 | `analyse_results.py` |
| T4 | Eval1 with Wilson intervals | 8.5 | `analyse_results.py` |
| T5 | Fisher exact matrix | 8.5 | `analyse_results.py` |
| T6 | Cost against quality | 8.8 | `analyse_results.py` |
| T7 | AutoBench comparison | 3.1 / 9.4 | paper + ours |

---

## Part E — Sequencing note

Phases 1–4 can be drafted without the Introduction being settled. If time runs short, the
order of sacrifice is: reduce Ch. 2 and 3 (background is the most compressible), never
reduce Ch. 6 or 9 — those two carry the argument.


---

## Part F — Page budget (9 chapters, ≤ 40 pp)

| Ch. | Title | Target pp |
|---|---|---|
| — | Title, abstract, contents | 3 |
| 1 | Introduction | 3.0 |
| 2 | Background and Related Work | 5.5 |
| 3 | System Design | 5.5 |
| 4 | The Static Localiser | 4.0 |
| 5 | Validating the Localiser | 4.0 |
| 6 | Experimental Design | 3.0 |
| 7 | Results | 6.5 |
| 8 | Discussion (incl. Threats to Validity) | 5.5 |
| 9 | Conclusion and Future Work | 2.0 |
| — | References | 1.5 |
| | **Total** | **~39.5** |

Page count is checked at the end of every phase with `pdfinfo`. If a phase overruns, the
overrun is absorbed in Chapter 2, never in Chapters 5 or 8.
