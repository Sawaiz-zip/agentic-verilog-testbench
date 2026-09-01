# Results

**S6.ReKI.1 — Agentic Verilog Testbench Generation with Pre-Simulation Error Localisation**
Muhammad Sawaiz Naveed · TU Ilmenau · supervised by Bing Wen

Consolidated findings from 220 pipeline runs across three sweeps plus an offline
fault-injection study. Every figure here is reproducible:

```bash
python scripts/analyse_results.py --all          # the cross-sweep numbers
python scripts/run_injection_study.py            # the localiser measurement
python scripts/render_report.py results/<sweep>  # per-sweep detail
```

---

## Summary

The static localiser works: it detects **93%** of injected structural faults with **zero**
false positives, including **30 faults that neither the compiler nor the simulator can
find**. But those faults are almost absent from real LLM output — **3 findings in 434
analyses** across two models and two circuit sets. **87% of real failures are semantic**
and require simulation by definition.

The central claim of the project therefore resolves as a **rigorous negative result**: the
technique is sound but its practical yield against current models is minimal. The
supporting measurements — a quantified variance floor, a control arm absent from prior
work, and a cost–quality curve — are the substantive contributions.

---

## 1. Experimental setup

| Sweep | Model (generation) | Circuits | Runs |
|---|---|---|---|
| `final_hard_r1` | `claude-sonnet-4.5` | 12 project fixtures (6 easy / 6 purpose-built hard) | 60 |
| `weak_model_r1` | `gpt-4o-mini` | same 12 | 60 |
| `verilogeval_weak` | `gpt-4o-mini` | 20 VerilogEval problems (AutoBench's benchmark) | 100 |

Temperature **0.7** throughout. Prompts frozen at tag `prompts-frozen` before any sweep;
none were modified afterwards. `gpt-4o-mini` handles classification, scenarios and mutants
in every configuration; only the generation/repair model changes between sweeps.

**Circuit selection for the VerilogEval sweep** was made *before* running, by structural
complexity (port count, width diversity, presence of sequential logic) — scores 26–42
against a full-set median of 18.7, with 15 of 20 sequential. Selecting on circuit
properties rather than on observed outcomes is what keeps the negative result valid: the
sample was deliberately biased *toward* the conditions where static faults are possible.

### Ablation arms

| Mode | Repairs when |
|---|---|
| `baseline` | never |
| `retry_only` | always once, **with no diagnostic information** — the control |
| `compiler_only` | `iverilog` reports an error |
| `pyverilog_only` | static analysis reports a finding |
| `hybrid` | any of static, compiler, or simulation |

`retry_only` is the arm that makes the comparison sound. Every repairing mode receives a
second generation that `baseline` does not, so a gain over `baseline` alone cannot separate
*"the feedback helped"* from *"a second attempt helped"*. **AutoBench's ablation has no such
control**, which is why its reported +8% (auto-debug) and +10% (scenario checking) cannot
distinguish the two either.

---

## 2. RQ1 — Which error categories appear, and which are detectable pre-simulation?

Across all 220 runs:

| Outcome | Count | Detectable without simulation? |
|---|---|---|
| Failed to compile | 20 | yes — the compiler finds these |
| **Compiled, failed simulation** | **133** | **no** |
| Passed | 67 | — |

**87% of failures are semantic.** Of 569 individual failing scenarios:

| Category | Count |
|---|---|
| sequence / FSM state | 95 |
| arithmetic / logic | 74 |
| boundary / overflow | 72 |
| reset / initialisation | 68 |
| timing / clocking | 51 |
| idle / hold | 3 |
| uncategorised | 206 |

Representative failures: `right_arithmetic_shift_2_positions`, `read_from_full_fifo`,
`simultaneous_read_write`, `overlapping_detection`. Each is a case where the model
misunderstood the circuit's behaviour in a corner case. The generated code is
well-formed; the *expected value* is wrong. No amount of reading the testbench reveals
this — the reference behaviour is external to the text.

> The category labels come from keyword matching on model-generated scenario names. They
> indicate the shape of the failures; they are not a hand-verified classification, and 206
> scenarios did not match any pattern.

---

## 3. RQ2 — How well does Pyverilog localise errors before simulation?

Two halves, and they point in opposite directions.

### 3a. Capability — measured by fault injection

14 known-good testbenches, 215 injected faults, three layers asked the same question.

| Fault class | n | static | compiler | simulator | **only static** |
|---|---|---|---|---|---|
| output never checked | 19 | **100%** | 0% | **0%** | **100%** |
| clock never toggled | 6 | **100%** | 0% | 17% | **83%** |
| wrong signal width | 22 | **100%** | 0% | 82% | **18%** |
| input never driven | 30 | **100%** | 0% | 97% | 3% |
| port left unconnected | 62 | **100%** | 0% | 98% | 2% |
| port bound to unknown name | 62 | **100%** | 100% | 0% | 0% |
| *edge sync removed* (control) | 5 | 0% | 0% | 80% | 0% |
| *two inputs swapped* (control) | 9 | 0% | 0% | 78% | 0% |
| **Total** | **215** | **93%** | **29%** | **56%** | **14%** |

- **93% localisation** — correct fault class *and* correct signal (exact match)
- **0 false positives** on all 14 clean testbenches
- **33/215 faults (15%) invisible to compiler and simulator together; static catches 30 (91%)**

The strongest single row is the first. A testbench that stops checking an output does not
fail — it **passes**, because it is no longer looking. The simulator cannot detect this by
construction and the compiler sees legal Verilog.

### 3b. Practical yield — measured on real generated testbenches

| Sweep | Analyses | Runs with ≥1 finding |
|---|---|---|
| Sonnet, project circuits | 82 | **0 / 60** |
| mini, project circuits | 79 | **1 / 60** |
| mini, VerilogEval circuits | 153 | **1 / 100** |
| Sonnet, VerilogEval circuits | 120 | **1 / 60** |
| **Total** | **434** (262 parsed) | **3 / 280** |

`pyverilog_only` performed **zero repairs in all three sweeps**. The single VerilogEval
finding (`Prob150_review2015_fsmonehot`, a 12-port one-hot FSM) landed in `compiler_only`,
a mode that ignores static findings by design, so it was never acted on. The same circuit
generated structurally clean testbenches in the other four modes — the fault was a random
generation slip, not a reproducible property.

**Both a weak and a strong model produce structurally well-formed testbenches.** The
"model is too capable for our checks" explanation is not supported: `gpt-4o-mini` is far
worse at the task (Eval1 63% → 35% on identical circuits) yet makes essentially the same
number of structural mistakes.

---

## 4. RQ3 — Can an LLM informed by static analysis repair effectively?

**The informed half is near-unanswerable**: with 3 findings in 434 analyses there was almost
nothing to inform it with. That absence is the finding.

**The comparison half**, pooled over 220 runs (n=44 per mode):

| mode | Eval1 | 95% CI (Wilson) |
|---|---|---|
| `pyverilog_only` | 20.5% | [11.2, 34.5] |
| `baseline` | 27.3% | [16.3, 41.8] |
| `retry_only` | 29.5% | [18.2, 44.2] |
| `compiler_only` | 34.1% | [21.9, 48.9] |
| **`hybrid`** | **40.9%** | [27.7, 55.6] |

Pairwise Fisher exact tests: **no comparison reaches p < 0.05.**

| comparison | p |
|---|---|
| hybrid vs baseline | 0.261 |
| **hybrid vs retry_only** (the honest control) | **0.372** |
| hybrid vs pyverilog_only | 0.063 (marginal) |

Hybrid is consistently highest and drives all effective repair (25 simulation-triggered,
8 compile-triggered, 0 static-triggered), but **the advantage is not statistically
supported at this sample size**.

### The variance floor

Arms performing zero repairs take an identical code path, so any difference between them
is pure sampling variation. Measured independently in two sweeps:

| sweep | identical-behaviour arms | spread |
|---|---|---|
| Sonnet, project circuits | 67%, 67%, 33% | **33 points** |
| mini, project circuits | 17%, 50%, 33% | **33 points** |

**At temperature 0.7 with n=12, differences below roughly 33 points are not
interpretable.** This is a methodological result in its own right, and it bears directly
on prior work: AutoBench reports single-run pass@1 comparisons without error bars.

### `retry_only` degrades compilation

On the hard VerilogEval circuits, blind regeneration produced **Eval0 70%** against 90–95%
for every other mode — it broke compilation in 6 of 20 runs. A second attempt *without*
information is worse than no second attempt.

---

## 5. RQ4 — Cost against quality

Mean per run, pooled over 220 runs:

| mode | tokens in | tokens out | wall | Eval1 | cost vs baseline |
|---|---|---|---|---|---|
| `pyverilog_only` | 6,025 | 3,676 | 40 s | 20.5% | −2% |
| `baseline` | 6,040 | 3,870 | 42 s | 27.3% | — |
| `compiler_only` | 6,554 | 3,911 | 43 s | 34.1% | +6% |
| `retry_only` | 7,982 | 4,797 | 55 s | 29.5% | +29% |
| `hybrid` | 9,776 | 5,103 | 61 s | 40.9% | **+50%** |

- **`compiler_only` is the efficiency winner**: +6% tokens for +7 points.
- **`hybrid` buys +14 points for +50% tokens and +45% wall time** — the best quality, at the
  worst cost, and not statistically separable from the control.
- **`pyverilog_only` costs essentially nothing and gains nothing.** Static analysis is
  almost free (deterministic, no LLM call, milliseconds) — consistent with a layer that
  fired three times in 434 analyses (262 of which the parser could read).

Total API expenditure for all experiments: **≈ $9.20**.

---

## 6. Comparison with AutoBench (Qiu et al., MLCAD 2024)

**We do not claim to outperform AutoBench.** The comparison is not clean: different model
(GPT-4-turbo vs Sonnet 4.5 / gpt-4o-mini), different circuit sample, and a non-comparable
Eval2.

| | AutoBench | This work |
|---|---|---|
| Eval0 pass@1 | 95.7% (SEQ 97.3%) | 95–100% | 
| Eval2 | 44.8% total | 82% (**not comparable**) |
| Circuits | 156 VerilogEval | 12 project + 20 VerilogEval |
| Static analysis | **none** | Pyverilog AST, 6 checks |
| Control arm | **none** | `retry_only` |

**Why the Eval2 comparison is void:** our testbenches caught 324 of 335 mutants (96.7%).
That is a ceiling. A pre-registered pilot showed it is **the circuits, not the mutants**:
regenerating mutants with a stronger model under AutoBench's own prompt moves the rate one
point (97.4%), while scoring the same testbenches against AutoBench's *published* mutants on
the benchmark circuits gives **53.8%** — a 44-point swing. Our fixtures are too small for a
mutant to hide in.

**What AutoBench actually does** for error detection: scenario-presence checking (does the
driver text contain each named scenario), auto-debug (compiler errors fed back), and a
`$fdisplay` standardisation script. None parses the Verilog.

**Their largest single gain is deterministic, not LLM-based**: sequential Eval0 rose from
55.47% to 97.33%, credited to the standardisation script. That is the same category as
this project's contribution — a mechanical pre-simulation fix — and it worked for them
because GPT-4-turbo genuinely omitted `$fdisplay`. Our equivalent finds nothing because
current models no longer omit it. **Same technique, different model generation, opposite
outcome.**

**Where this work is methodologically stronger:** a no-diagnostics control arm, a
fault-injection measurement of the localiser rather than an assertion that it works, a
quantified variance floor, and cross-model evidence.

---

## 7. Threats to validity

- **Sample size.** 12 and 20 circuits; n=44 per mode pooled. Underpowered against a
  33-point variance floor.
- **Single repeat per sweep.** Replication would narrow intervals; three sweeps
  nonetheless converged on the same qualitative picture.
- **Prompt tuning.** `gen_driver.j2` was tuned on the six original project fixtures. The six
  purpose-built hard circuits and all 20 VerilogEval problems were never used for tuning.
- **Eval2 is at ceiling** (99.5% mutants caught) and does not discriminate between modes.
  Mutants are LLM-generated per run; harder deterministic mutation operators would fix this.
- **Failure categories are keyword-derived**, not hand-verified; 206 of 569 unmatched.
- **Cross-model comparison is confounded**: `gpt-4o-mini` differs from Sonnet 4.5 in more
  than capability alone.

---

## 8. Findings

1. **The static localiser is sound.** 93% detection, 93% localisation, 0 false positives,
   and 30 faults invisible to both compiler and simulator — measured by fault injection,
   not asserted.
2. **Structural faults are rare in practice.** 3 findings in 434 analyses, across two
   models and two circuit sets including the field's standard benchmark.
3. **Failures are overwhelmingly semantic** — 133 of 153, requiring simulation by definition.
4. **Blind retry can harm.** `retry_only` dropped Eval0 to 70% against 90–95% elsewhere.
5. **No mode beats the control at n=44** (hybrid vs `retry_only`, p=0.372), against a
   measured 33-point variance floor reproduced in two independent sweeps.
6. **Static analysis is nearly free and nearly useless here**; compiler feedback is the
   efficiency winner; simulation feedback drives every effective repair.

The value of pre-simulation structural analysis is bounded not by the technique but by the
error profile of the generator. Against models that produce structurally well-formed
output, that profile leaves little for it to find.
