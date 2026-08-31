# Eval2 mutant-quality pilot — pre-registered criteria

**Written 2026-08-28, before any mutant was generated or scored.**
Recorded in advance so that the decision to adopt or reject a mutant generator
cannot be made on the basis of the Eval2 score it produces.

## Why this pilot exists

Eval2 currently reports 324/335 (97%) caught, which discriminates nothing and is
reported in the report as a limitation rather than a result. Scoring the same
testbenches against AutoBench's published mutants gives 43/80 (54%), which
establishes that the ceiling is a property of our mutant generator and not of our
testbenches.

AutoBench's mutants cover only the 20 VerilogEval circuits (8 of our 67
Eval1-passing runs). The other 59 runs are project fixtures for which no published
mutants exist, so a better generator is needed for those.

## Two candidate causes, tested separately

| Condition | Model | Call structure |
|---|---|---|
| **A** (current) | cheap (`gpt-4o-mini`) | 5 independent calls, one mutant each |
| **B** | cheap (`gpt-4o-mini`) | 1 batched call for 10, AutoBench's prompt |
| **C** | strong (`claude-sonnet-4.5`) | 1 batched call for 10, AutoBench's prompt |

A vs B isolates call structure. B vs C isolates model. AutoBench's prompt
(`config/templates/script_template/mutant_template.txt`, their repo) asks for all
n mutants in one response and explicitly instructs the model to spread changes
across positions and modification types. Our prompt asks five times independently,
which applies no diversity pressure.

Pilot circuits: `alu_1bit`, `bcd_to_7seg` (10 Eval1-passing runs each) and `dff`
(sequential, 6 runs). 26 of the 59 project-fixture runs.

## Acceptance criteria — about mutant quality, NOT about our score

A condition is adopted on these grounds only:

1. **Validity ≥ 80%.** A mutant is valid if it compiles against a known-good
   testbench AND is non-equivalent, i.e. its simulated behaviour differs from the
   golden design on at least one input. Equivalent mutants are undetectable by any
   testbench and must be excluded from the denominator, not counted as misses.
   (AutoBench's published set does not do this: it contains at least one mutant
   annotated "No change in functionality, just a comment added.")
2. **Positional diversity.** The mutants of a circuit must touch more than one
   distinct source line. Five copies of the same change is one mutant, not five.
3. **Header integrity.** No mutant may alter the module header. A port-list change
   is an interface break, not a behavioural bug, and would be caught trivially.

Ranking among conditions that pass: higher validity first, then higher positional
diversity. **The Eval2 score the condition produces is not a criterion.**

## What is NOT a legitimate reason to reject a condition

Producing an Eval2 score that is lower, higher, or otherwise less convenient than
the current 97%. Once a generator passes the criteria above, whatever score falls
out of it is the measurement, and it goes in the report unchanged.

## Decision rule

- If any condition passes all three criteria → adopt the best-ranked one, regenerate
  mutants for all 11 project-fixture circuits, rescore the 59 runs, report the result.
- If no condition passes → keep the existing mutants and the existing text, and report
  the pilot itself as a strengthened statement of the limitation.

Either outcome is written up. The pilot is not repeated with adjusted prompts until
a preferred number appears.

## Scope limit, acknowledged in advance

Eval2 is scored only on Eval1-passing runs, and the five ablation arms have
different numbers of those (hybrid 18, pyverilog_only 9). Conditioning on Eval1
is a selection effect, so no version of this pilot licenses a comparison of Eval2
across arms. What it can support: a valid characterisation of testbench quality,
and a comparison against AutoBench.
