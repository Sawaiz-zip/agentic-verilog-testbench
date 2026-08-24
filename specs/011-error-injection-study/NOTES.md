# 011 — Error-Injection Study (Day 3, FR-017)

**Date:** 2026-08-24 · **Branch:** `011-error-injection-study`
**Raw data:** `results/injection_study_final.json` · **Cost:** zero tokens (fully offline)

The first direct measurement of the static localiser. Answers **RQ2** ("can Pyverilog
analysis narrow down testbench errors before simulation?") with numbers rather than
inference from end-to-end pass rates.

## Method

End-to-end pass rates cannot answer RQ2: a testbench either passes or it does not, and
when it fails we cannot tell which faults the analyser *could* have caught. So we measure
the analyser directly. Take a testbench already known to pass, break it in one known way,
and ask three layers the same question:

| layer | question |
|---|---|
| **static** | does the Pyverilog analyser flag it? |
| **compiler** | does `iverilog -g2012` refuse to compile it? |
| **simulator** | does `vvp` fail against the golden DUT? |

The three-way comparison is what makes the result meaningful. A fault only the static
analyser catches is one the existing tooling cannot find at all; a fault the compiler
already catches is one our layer adds nothing to.

**Corpus:** 14 circuits, each the LLM-generated testbench from a recorded passing run,
re-verified to compile and pass against the **golden** DUT before use.
**Faults:** 215, from 8 injectors covering every taxonomy class plus two negative controls.

## Results

**Baseline (14 unmutated testbenches): 14/14 parsed, 0 false positives → 100% precision
on clean input.**

| fault class | n | static | compiler | sim | **only static** |
|---|---|---|---|---|---|
| `unobserved_output` | 19 | **100%** | 0% | 0% | **100%** |
| `remove_clock_generator` | 6 | **100%** | 0% | 17% | **83%** |
| `width_change` | 22 | **100%** | 0% | 82% | **18%** |
| `undriven_input` | 30 | **100%** | 0% | 97% | 3% |
| `port_drop` | 62 | **100%** | 0% | 98% | 2% |
| `port_rename` | 62 | **100%** | 100% | 0% | 0% |
| `break_edge_sync` *(control)* | 5 | 0% | 0% | 80% | 0% |
| `swap_bindings` *(control)* | 9 | 0% | 0% | 78% | 0% |
| **TOTAL** | **215** | **93%** | **29%** | **56%** | **14%** |

- **Localisation (correct class AND correct signal): 201/215 = 93%.** Exact signal match,
  not substring — naming *which* signal is wrong is what gives the repair prompt somewhere
  to act.
- **33/215 (15%) of faults are missed by the compiler and the simulator together.
  Static analysis catches 30 of those 33 (91%).**

### The headline: two classes only static analysis can see

**`unobserved_output` — 19 faults, static 100%, compiler 0%, simulator 0%.**
A testbench that stops checking an output does not fail; it **passes**, because it is no
longer looking. The simulator cannot detect this by construction — there is nothing to
observe — and the compiler sees legal Verilog. This is RQ2 demonstrated: a real, common
testbench defect that only pre-simulation analysis can find.

**`remove_clock_generator` — 6 faults, static 100%, simulator 17%.**
A clock assigned once and never toggled produces a simulation that runs but never
advances. Every scenario reads back the reset value, and five of six such testbenches
still *passed* their own checks.

**`width_change` — 22 faults, compiler 0%.** Verified directly: `iverilog` exits 0 on a
port width mismatch, emitting only `warning: Port ... expects 4 bit(s), given 3`. The
simulator misses 18% — the cases where the truncated bits are never exercised.

### The honest limits

- **`port_rename`: static 100%, compiler 100%.** We add nothing here but speed. Worth
  stating plainly; it is 62 of the 215 faults.
- **`swap_bindings` (negative control): static 0%, by design.** Swapping two same-width
  inputs leaves both connections legal — a semantic error, not a structural one. No static
  check can see it; the simulator caught 78%. This marks the boundary of the approach.
- **14 circuits, 8 self-chosen fault classes.** Real evidence, not a benchmark result.

## Negative result: the sensitivity-list check is removed

`sensitivity_list_error` **caught 0 of 5** injected `break_edge_sync` faults — the exact
defect it existed to detect — and had produced the study's only baseline false positive,
on a passing testbench.

The cause is structural: it inspected `always` blocks *inside the testbench*. Real
LLM-generated testbenches drive everything from `initial` blocks and synchronise with
`@(posedge clk)`, so the check was looking where the evidence never is.

It is removed from the taxonomy. The concern it aimed at is covered better by
`CLOCK_NEVER_TOGGLED` (6/6). Keeping a check with zero measured recall and a history of
false positives would mean claiming a capability we do not have. `PyverilogReport.
sensitivity_errors` is renamed `clock_errors` to match what the bucket now holds, and
`test_missing_edge_synchronisation_is_a_known_blind_spot` records the resulting gap so it
is not rediscovered as a bug. The simulator catches 80% of these, which is why the gap is
acceptable.

**Six checks remain, all injection-verified.**

## Eight defects the study found in already-tested code

Building the experiment was itself the most productive part of the day. Nothing here was
visible to the existing test suite.

*In the harness — these would have inflated the numbers:*

1. **Corpus used the generated DUT, not the golden one.** A recorded run stores the DUT
   the pipeline generated, which can itself be malformed. One was, and its compile error
   scored as "the compiler detected my injected fault".
2. **No baseline gate.** Entries are now re-verified to compile and pass before injection;
   failures are excluded and reported. Measuring against an already-failing baseline
   attributes the baseline's problems to the fault.
3. **`_dut_port_directions` mis-parsed shared declarations.** `input [7:0] a, input [7:0] b`
   returned `{a, input, op, "output reg", zero}` — two real ports lost, two invented.
   Injectors that branch on direction silently skipped them, shrinking the denominator.

*In the analyser — these were deflating the numbers, and hiding real defects:*

4. **String literals and comments were read as code.** `$display("PASS: addition_boundary_overflow")`
   made the `overflow` output look observed; `$fdisplay(f, "clk=%b", clk)` made a dead
   clock look like it was toggling. Same class as the Eval1 verdict decided by a scenario
   named `immediate_mismatch`. Fixed with `verilog_text.strip_noise()`, which blanks
   comment and string contents while preserving length and line breaks.
   **`unobserved_output` went from 47% to 100%.**
5. **The 009 sensitivity fix was incomplete.** Pyverilog gives `always #5 clk = ~clk;` a
   Sens of type `"all"` with no signal, not an empty list — so a clock generator still
   counted as a sensitised block with no edge trigger, the false positive above.
6. **The clock-toggle search used a fixed 400-character window.** It overran a short
   `always @(*)` block and credited it with a `clk = 0;` from a separate `initial` block.
7. **"More than one assignment" counted as toggling.** A testbench writing `clk = 0;` in
   two places has a dead clock, not a running one. Now requires *distinct* assigned values,
   which still accepts a generator written without `~`.
8. **The clock-generator injector matched one style.** Five of six sequential testbenches
   write `forever #5 clk = ~clk;` inside an initial block, so this class was measured on a
   sample of **one**. After the fix: 6 injectable, 6 detected — the row went from 0% to
   100%.

Defects 4–8 mean the Day-2 figures were produced by a partly broken localiser. The
injection study is what surfaced that, which is the argument for having run it.

## Validation

Full suite: **182 passed, 3 skipped** (was 153 at the start of Day 3). New: the injection
module and its tests, `verilog_text` and its tests, and regression tests for every defect
above.

## Files

| Path | Purpose |
|---|---|
| `pipeline/analysis/fault_injection.py` | 8 injectors; returns `Fault(kind, expected_type, signal, description, testbench)` |
| `pipeline/analysis/verilog_text.py` | `strip_noise()` — blanks comments and string contents, preserving offsets |
| `scripts/run_injection_study.py` | runs the study; `--report-only` re-renders tables from saved data |
| `results/injection_study_final.json` | raw per-fault records |
