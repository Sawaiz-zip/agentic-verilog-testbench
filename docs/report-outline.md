# Report Outline — S6.ReKI.1

**Working document.** Structure, metrics placement, and the argument each chapter must
carry. Every figure cited here exists in `docs/results.md` and is reproducible from
`scripts/analyse_results.py`, `scripts/run_injection_study.py`, `scripts/render_report.py`.

---

## The argument in one line

*We built a pre-simulation error localiser, proved it works, found it has almost nothing
to find, and established why — the failure profile of LLM-generated testbenches is
semantic, not structural.*

## Narrative arc (why the chapters are ordered this way)

1. A plausible hypothesis — and it **was** plausible: AutoBench's single largest gain came
   from exactly this kind of mechanical pre-simulation fix.
2. Build the pipeline and the localiser.
3. **Validate the instrument.** A null reading from an unvalidated detector means nothing.
4. Apply it at scale — find almost nothing.
5. **Systematically rule out the alternative explanations** (model too strong? circuits too
   easy? benchmark unrepresentative?). This is what turns "it didn't work" into evidence.
6. Explain the real cause and extract the transferable lesson.

**The negative result is stated in the Introduction, not withheld until Chapter 8.** A
reader who knows the destination reads the method chapters as *"how they established
this"* rather than waiting for a payoff that never comes.

---

## Chapter structure

### 1. Introduction  (~4 pp)
- 1.1 Verification is the bottleneck — 49% of design engineer time (Wilson Research Group)
- 1.2 LLMs can write testbenches, but the failure mode is *silent*: syntactically valid,
      functionally wrong. It compiles, runs, reports success, and tested nothing.
- 1.3 The hypothesis: some of these faults are visible **without simulation**, so a static
      pass could localise them earlier and cheaper than a simulate-and-retry cycle
- 1.4 Research questions (RQ1–RQ4)
- 1.5 **What this work found** — state it plainly here:
      the localiser detects 93% of injected structural faults with zero false positives,
      including 30 that neither compiler nor simulator can see; but it fired **twice in 314
      analyses** of real generated testbenches; 87% of real failures are semantic
- 1.6 Contributions (five, with the corrected scope on #5)
- 1.7 Report roadmap

### 2. Background  (~5 pp)
- 2.1 Simulation-based verification and the role of the testbench
- 2.2 What makes a testbench *wrong*: the structural / semantic distinction
      → **the pivotal concept of the whole report — define it here with the code example**
- 2.3 LLM code generation for HDL: capabilities and known failure modes
- 2.4 Static analysis of Verilog: Pyverilog AST and dataflow; Verible as fallback
- 2.5 Evaluation vocabulary: Eval0 (compiles), Eval1 (passes against reference),
      Eval2 (detects injected DUT bugs)

### 3. Related Work  (~4 pp)
- 3.1 AutoBench (Qiu et al., MLCAD 2024) — the seed work, in detail
  - pipeline stages; the three self-enhancement mechanisms
  - reported results: Eval0 95.7%, Eval2 44.8% (CMB 62.2% / SEQ 26.0%)
  - **what it does not do:** no Verilog parsing anywhere; no control arm in its ablation
- 3.2 Other LLM-for-HDL work: VerilogEval, AutoChip, ChipGPT, Chip-Chat, LLM4DV
- 3.3 Mutation testing as an evaluation methodology
- 3.4 **Gap statement** — where this work sits and what it adds

### 4. System Design  (~8 pp) — *primary contribution*
- 4.1 Why a graph, not a script: explicit state, explicit edges, no hidden control flow
- 4.2 Graph topology (figure) and the typed state schema
- 4.3 Generation stages: classify → gen_dut → extract_spec → gen_scenarios →
      gen_driver ∥ gen_checker → merge
- 4.4 Deterministic standardiser — a Python AST pass, not an LLM, and why
- 4.5 The repair loop: three feedback sources, bounded iterations, oscillation detection,
      best-so-far retention (a later repair can never yield a worse reported artifact)
- 4.6 Evaluation harness: budget guard, daily-rate-limit and out-of-credit aborts
- 4.7 Engineering practices: frozen prompt templates, per-call telemetry, offline test suite

### 5. The Static Localiser  (~6 pp)
- 5.1 Design principle: **detect only what reading the code can establish**
- 5.2 The six checks — for each: what it detects, and whether compiler/simulator could
      (`port_binding_mismatch`, `width_mismatch`, `undriven_input`, `unobserved_output`,
      `missing_fdisplay`, `clock_never_toggled`)
- 5.3 **A check that was removed** — `sensitivity_list_error`: 0/5 recall plus a false
      positive on a passing testbench. Report the removal and the evidence for it.
- 5.4 False positives are the real enemy — four were found and fixed during development;
      the string-literal defect (scenario names read as code) suppressed detection outright
- 5.5 Parse robustness: Pyverilog on LLM output, Verible fallback

### 6. Validating the Instrument — Fault Injection  (~6 pp)
> **Placed before the empirical study on purpose.** A null result from an unvalidated
> detector is uninterpretable.
- 6.1 Why end-to-end pass rates cannot answer RQ2
- 6.2 Method: known-good testbench → inject one known fault → ask three layers
- 6.3 The eight injectors, including two **negative controls**
- 6.4 Methodological safeguards: mutations must be legal Verilog; corpus re-verified before
      injection; golden DUTs not generated ones
- 6.5 Results — the three-layer table
- 6.6 The decisive class: `unobserved_output`, 100% static / 0% compiler / 0% simulator
- 6.7 Honest boundaries: `port_rename` is caught by the compiler too; swapped same-width
      inputs are undetectable by design

### 7. Experimental Design  (~5 pp)
- 7.1 Three sweeps: 220 runs (Sonnet ×12 circuits, mini ×12, mini ×20 VerilogEval)
- 7.2 Circuit sets, and **how the VerilogEval 20 were chosen — by structural complexity,
      before running.** Explain why selecting on outcomes would void the result.
- 7.3 The five ablation arms
- 7.4 **Why `retry_only` exists** — every repairing mode gets a second generation baseline
      does not; without this control a gain cannot be attributed to the feedback.
      Note explicitly that AutoBench's ablation lacks one.
- 7.5 Prompt freezing (`prompts-frozen` tag) and what it protects against
- 7.6 Statistical treatment: Wilson intervals, Fisher exact tests, and why not chi-square

### 8. Results  (~10 pp)
- 8.1 Pipeline reliability: 220/220 runs, zero harness errors
- 8.2 **RQ1** — failure origins: 20 structural vs 133 semantic (87%); 569 failing scenarios
      categorised
- 8.3 **RQ2a — capability:** 93% detection, 93% localisation, 0 FP, 30/33 faults invisible
      to compiler and simulator
- 8.4 **RQ2b — practical yield:** 2 findings / 314 analyses; `pyverilog_only` never repaired
- 8.5 **RQ3** — ablation with confidence intervals; no pairwise difference at p<0.05;
      hybrid vs control p=0.372
- 8.6 **The variance floor** — 33 points, measured twice independently. Present as a
      standalone finding, not a caveat.
- 8.7 `retry_only` degrades compilation (Eval0 70% vs 90–95%) — blind retry can harm
- 8.8 **RQ4** — cost against quality; `compiler_only` as efficiency winner
- 8.9 Cross-model and cross-benchmark consistency

### 9. Discussion  (~7 pp)
- 9.1 **Ruling out the alternative explanations** — the chapter that makes the result stick
  - *"the model was too capable"* → refuted: mini is far worse at the task (Eval1 63%→35%)
    yet makes the same number of structural mistakes
  - *"your circuits were too easy"* → refuted: 20 VerilogEval circuits chosen for maximum
    structural complexity, 15/20 sequential, still nothing
  - *"your detector is broken"* → refuted: 93% on injected faults, independently re-verified
  - *"you looked in the wrong place"* → the checks cover the classes prior work needed
- 9.2 Why LLMs produce structurally correct testbenches — pattern-following vs reasoning
- 9.3 **Same technique, different era, opposite outcome** — AutoBench's biggest win was a
      deterministic `$fdisplay` standardiser (SEQ Eval0 55%→97%) because GPT-4-turbo omitted
      it. Current models do not. Tooling value tracks the generator's error profile, and
      that profile is a moving target.
- 9.4 Implication: the value of static analysis is inversely proportional to generator
      maturity — with the caveat that it becomes valuable again for weaker/smaller/local models
- 9.5 On measurement: single-run pass@1 without error bars is unsafe at this variance
- 9.6 What this means for practitioners: spend on simulation feedback, not static analysis,
      when using frontier models

### 10. Threats to Validity  (~3 pp)
- Construct: Eval2 at a 99.5% ceiling; keyword-derived failure categories (206/569 unmatched)
- Internal: prompt tuned on 6 of 12 project fixtures; cross-model comparison confounded
- External: 12 + 20 circuits; two models; one provider
- Statistical: n=44/mode against a 33-point variance floor; single repeat per sweep
- **Corrections made during the work** — false positives found and fixed, two premature
  conclusions retracted. Including these strengthens credibility rather than weakening it.

### 11. Conclusion and Future Work  (~3 pp)
- 11.1 Summary against each RQ
- 11.2 The six findings
- 11.3 Contributions restated, with #5's corrected scope
- 11.4 Future work: harder deterministic mutants; semantic checking against the spec
      (property/assertion generation); weaker and local models where structural faults may
      persist; larger n to resolve the hybrid gap; per-node origin attribution

---

## Metrics inventory — what appears where

| Metric | Value | Chapter |
|---|---|---|
| Runs, harness errors | 220, 0 | 8.1 |
| Structural vs semantic failures | 20 vs 133 (87%) | 8.2 |
| Failing scenarios categorised | 569 | 8.2 |
| Injection detection / localisation | 93% / 93% | 6.5, 8.3 |
| False positives on clean input | 0 / 14 | 6.5, 8.3 |
| Faults invisible to compiler+simulator | 33/215; static catches 30 (91%) | 6.5, 8.3 |
| `unobserved_output` three-layer | 100% / 0% / 0% | 6.6, 8.3 |
| Static findings in real output | 2 / 314 analyses | 8.4 |
| `pyverilog_only` repairs | 0 in all sweeps | 8.4 |
| Eval1 per mode + Wilson 95% CI | 20.5–40.9% | 8.5 |
| Fisher exact, hybrid vs control | p = 0.372 | 8.5 |
| Variance floor | 33 pts, ×2 sweeps | 8.6 |
| `retry_only` Eval0 on hard circuits | 70% vs 90–95% | 8.7 |
| Token cost per mode | +50% hybrid, +6% compiler_only | 8.8 |
| Repair feedback sources | 25 sim / 8 compile / 0 static | 8.4, 8.8 |
| Eval2 mutants | 189/190 (ceiling — a limitation) | 10 |
| Pyverilog parse success | 81/82, 153/153 | 5.5 |
| Total API spend | ≈ $9.20 | 8.8 |

**Report Eval2 as a limitation, not a result.** At 99.5% it discriminates nothing, and
quoting 82% against AutoBench's 44.8% would be misleading.

---

## Conclusion — what it should say

Four movements:

**1. What was built.** A graph-based testbench generation pipeline with an explicit repair
loop, a deterministic standardiser, a six-check pre-simulation localiser, and an evaluation
harness. 220 runs, zero harness errors.

**2. The two-part answer to RQ2 — the core result.**
> Pre-simulation static analysis detects structural testbench faults reliably — 93% of
> injected faults, 93% localised to the correct signal, zero false positives, and 15% of
> faults invisible to both compiler and simulator. In 314 analyses of real
> LLM-generated testbenches across two models and two circuit sets, it fired twice.

**3. The explanation, and the transferable lesson.** LLM testbench failures are
overwhelmingly semantic (87%). Models follow the *form* of a testbench reliably while
misjudging expected values and timing. The value of structural static analysis is therefore
bounded by the generator's error profile — and that profile shifts with each model
generation. AutoBench's largest gain came from precisely this class of mechanical fix,
because GPT-4-turbo made the mistakes it corrected. Two years later those mistakes are
gone. **Auxiliary tooling for LLM output has a shelf life, and its value must be
re-measured, not assumed.**

**4. The methodological contribution.** A no-diagnostics control arm — absent from the
prior work this builds on — showed that no mode's advantage survives significance testing.
A variance floor of 33 points, measured twice independently, shows why single-run pass@1
comparisons at this sample size are unsafe. Both are reusable by anyone evaluating
LLM-generated code.

**Closing line, roughly:** the negative result is not that the technique fails, but that
the problem it solves has largely been solved by the generators themselves — and
establishing that required building the technique, proving it works, and then finding it
idle.
