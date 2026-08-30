# 6. Our Experiments and Results

Two separate experiments, in this order for a reason.

---

## 6.1 Why the order matters

We ran the fault-injection study **before** the big sweeps, and the report presents it that
way too.

**The reason:** the main result is *"our tool found almost nothing."* That statement is
worthless unless you already know the tool works. A broken detector also finds nothing.

So: prove the instrument first, then take the reading.

> If your professor asks why Chapter 5 comes before Chapter 7 in the report, this is the
> answer. **A null reading from an unvalidated instrument is uninterpretable.**

---

## 6.2 Experiment 1 — the fault-injection study

### What we did

Take a testbench that **already works**. Break it in one **known** way. Ask three things:

1. Does our static analyser notice?
2. Does `iverilog` refuse to compile it?
3. Does the simulation fail?

**Corpus:** 14 testbenches, one per circuit, taken from real runs that passed Eval1. Real
AI-generated artefacts, not hand-written examples — because a hand-written testbench would
carry our own assumptions about what testbenches look like, and those assumptions are exactly
what the checks encode.

**Faults injected:** 215, from 8 injectors.

### How we broke them — this is the "how did you make it faulty" answer

Six injectors target a specific check:

| Injector | What it does to the testbench |
|---|---|
| `port_rename` | change `.op(op)` to `.opcode(op)` — a port name the circuit lacks |
| `port_drop` | delete a port connection entirely |
| `width_change` | narrow a declared signal, e.g. `reg [7:0]` → `reg [6:0]` |
| `undriven_input` | redirect an input's assignments to a dummy register so the input is never set |
| `unobserved_output` | remove an output from the comparisons so it is no longer checked |
| `remove_clock_generator` | delete the `always #5 clk = ~clk;` line |

Two are **negative controls** — deliberately undetectable:

| Control | Why it cannot be caught by reading |
|---|---|
| `break_edge_sync` | replaces every `@(posedge clk)` with a bare delay |
| `swap_bindings` | binds two same-width inputs to each other's signals — every connection is still legal and correctly typed; only the *meaning* is wrong |

**Why include faults we know we cannot catch?** Because a study containing only detectable
faults reports a detection rate that describes the study design, not the method. The controls
mark where the real boundary falls.

### Three safeguards, each added after we made the mistake

1. **Mutations must produce legal Verilog.** An injector that emits a syntax error would score
   as *"the compiler caught it"* for a defect the injector created. That is why
   `undriven_input` redirects assignments rather than deleting statements — deleting can empty
   an `if` branch.
2. **Use the golden circuit, not the generated one.** An early version compiled mutated
   testbenches against the *pipeline's own* generated circuit. One of those was malformed, and
   its compile error was scored as a detection of our injected fault.
3. **Verify every corpus entry before injecting.** The unmutated testbench must compile and
   pass. Measuring against an already-failing baseline attributes the baseline's problems to
   the injected fault.

### The results

| Fault class | n | static | compiler | simulator | **only static** |
|---|---|---|---|---|---|
| output never checked | 19 | **100%** | 0% | **0%** | **100%** |
| clock never toggled | 6 | **100%** | 0% | 17% | 83% |
| wrong signal width | 22 | **100%** | 0% | 82% | 18% |
| input never driven | 30 | **100%** | 0% | 97% | 3% |
| port left unconnected | 62 | **100%** | 0% | 98% | 2% |
| port bound to unknown name | 62 | **100%** | 100% | 0% | 0% |
| *edge sync removed* (control) | 5 | 0% | 0% | 80% | 0% |
| *inputs swapped* (control) | 9 | 0% | 0% | 78% | 0% |
| **Total** | **215** | **93%** | **29%** | **56%** | **14%** |

**Three headline numbers:**

- **93% detection**
- **93% localisation** — it named the correct fault class *and* the correct signal. Exact
  match required: reporting `a` does not count as localising a fault in `data`.
- **0 false alarms** on all 14 unmutated testbenches

**And the one that matters most:** 33 of 215 faults (15%) were caught by **neither the
compiler nor the simulator**. Static analysis caught **30 of those 33 — 91%**.

### The honest bits

- **`port_rename` is 100% static but also 100% compiler.** 62 of 215 faults are in that class,
  so a big chunk of the headline rate describes work the compiler already does. We add speed,
  not capability.
- **Both controls scored 0%, as designed.** The simulator caught 78–80% of them. That is the
  correct division of labour.

**Conclusion: the tool works.**

---

## 6.3 Experiment 2 — the three sweeps

### What we ran

| Sweep | Model writing the code | Circuits | Runs |
|---|---|---|---|
| `final_hard_r1` | `claude-sonnet-4.5` | 12 of ours | 60 |
| `weak_model_r1` | `gpt-4o-mini` | the same 12 | 60 |
| `verilogeval_weak` | `gpt-4o-mini` | 20 VerilogEval | 100 |
| | | **32 circuits** | **220 runs** |

Each = circuits × 5 configurations. Temperature 0.7 throughout. Prompts frozen at a tagged
commit beforehand.

**The design changes one thing at a time.** Sweeps 1→2 hold circuits fixed, change the model.
Sweeps 2→3 hold the model fixed, change the circuits.

### How the 20 benchmark circuits were chosen — important for validity

Every one of the 156 problems was scored **before any run took place**, on three properties of
its circuit: port count, number of distinct signal widths, and whether it has a clock. We took
the top 20.

Result: complexity scores 26–42 against a median of 18.7, port counts 6–12, and **15 of 20
sequential**.

**Why this way?** Structural faults are only *possible* where structure is complex. So this
deliberately biases the sample **towards** the conditions where our tool can succeed.

**Why not just run all 156 and report the 20 that gave findings?** Because that would be
selecting on the *outcome*. It would produce a better-looking number that means nothing, and
it would not survive the first question about how the circuits were chosen.

> A null result obtained under **favourable** conditions is much stronger than one obtained
> under arbitrary conditions. That is the whole point.

---

## 6.4 The main result

**Static analysis fired on three runs in the 237 analyses where its checks could actually run.**

| Sweep | Analyses | Checks actually ran | Runs with a finding |
|---|---|---|---|
| Sonnet, our circuits | 82 | 75 | **0 / 60** |
| mini, our circuits | 79 | 51 | **1 / 60** |
| mini, VerilogEval | 153 | 64 | **1 / 100** |
| **Sonnet, VerilogEval** | 120 | 72 | **1 / 60** |
| **Total** | **434** | **262** | **3 / 280** |

### The fourth sweep — the strong model on the benchmark circuits

Added 2026-08-29 to close the one empty cell in the design: the strong model had only ever run
on our own fixtures, never on the benchmark. Same pipeline, same frozen prompts, same 20
circuits — **only the model changed**.

| | gpt-4o-mini | **Sonnet 4.5** |
|---|---|---|
| baseline Eval1 | 10% | **25%** |
| retry_only Eval1 | 10% | **30%** |
| hybrid Eval1 | 10% | **50%** |
| runs with a static finding | 1 / 100 | 1 / 60 |

**The control arm earned its place.** `retry_only` gets a second attempt but is told nothing
about what went wrong. It scored 30% against baseline's 25% — **McNemar p = 1.000**. The bare
extra attempt is worth nothing. Since `hybrid` *also* gets that extra attempt, the 20 points
separating it from `retry_only` sit on **the diagnosis**, not on resampling.

That comparison now exists in two independent samples and agrees in both:

| sample | hybrid wins | control wins | McNemar |
|---|---|---|---|
| ablation, 44 circuits | 6 | 1 | p=0.125 |
| benchmark, 20 circuits | 5 | 1 | p=0.219 |
| **stratified, 64** | **11** | **2** | **p=0.023** |

⚠️ **Say this carefully.** The p=0.023 is *post hoc* — we ran the sweep, saw hybrid leading,
then added the control, then pooled. It does not survive Bonferroni for the 11 comparisons
made. The honest line is: *"directionally consistent across two independent samples, stratified
p=0.023, reported as suggestive rather than established."* Do not say "we proved hybrid works."

**Eval1 moved 25 points. The structural yield did not move.** That is the cleanest single
statement of this project's central finding: model capability controls whether a testbench is
*right*, not whether it is *well-formed*.

Two more things from this sweep:

- **A static finding triggered a repair — the only time in 260 runs.** On the 12-port one-hot
  FSM, the localiser correctly reported `clk` and `reset` unconnected, hybrid repaired on that
  basis, and two iterations later they were *still* unconnected. Exercised once; did not work.
- **A live lesson in variance.** At 9 of 20 circuits, hybrid stood at 89%. It finished at 50%.
  Nothing changed but the sample size. If asked why you insist on error bars, tell this story.

**Why two denominators?** Pyverilog could not parse 124 of the 314 files. In those we fell
back to Verible, which only checks syntax — so no structural check ran, even though the record
says the analysis succeeded (see doc 03). **Quote 2-in-190, not 2-in-314.** The unqualified
figure understates the rate by a factor of 1.65 and an examiner who checks will find it.

`pyverilog_only` — the configuration whose entire purpose is to act on static findings —
performed **zero repairs across 44 runs**. It never had anything to act on.

Meanwhile, plenty of testbenches *were* wrong:

| Outcome | Runs |
|---|---|
| Failed to compile | 20 |
| **Compiled, then failed simulation** | **133** |
| Passed | 67 |

**87% of failures are semantic.** They compile fine and test the wrong things.

The failing scenarios — `right_arithmetic_shift_2_positions`, `read_from_full_fifo`,
`overlapping_detection` — are all cases where the model misjudged how the circuit behaves in a
corner case. You cannot see that by reading.

---

## 6.5 Ruling out the alternative explanations

This is what makes it a result rather than a failed experiment.

| "But maybe…" | What we did | What happened |
|---|---|---|
| **the model was too good** | ran `gpt-4o-mini` on identical circuits | Much worse at the task (Eval1 67% → 17%) but **structurally just as tidy**. Findings 0 → 1. |
| **your circuits were too easy** | 20 benchmark circuits picked for max complexity | **1 finding in 153 analyses** |
| **your detector is broken** | the injection study | 93% detection, 0 false alarms, re-verified after the sweeps |
| **you looked for the wrong faults** | — | AutoBench's biggest fix targets exactly our `missing_fdisplay` class |

**The "too capable model" explanation is refuted, and that surprised us.** The weak model is
far worse at the job but makes the *same* structural mistakes — essentially none. Capability
affects whether the testbench is **right**. It does not affect whether it is **well-formed**.

---

## 6.6 The ablation, and why we cannot claim a win

Pooling all 220 runs, 44 per configuration:

| Mode | Eval1 | 95% confidence interval |
|---|---|---|
| `pyverilog_only` | 20.5% | [11.2, 34.5] |
| `baseline` | 27.3% | [16.3, 41.8] |
| `retry_only` | 29.5% | [18.2, 44.2] |
| `compiler_only` | 34.1% | [21.9, 48.9] |
| **`hybrid`** | **40.9%** | [27.7, 55.6] |

`hybrid` is highest. But **every interval overlaps every other**, and no pairwise test reaches
significance:

- hybrid vs baseline: **p = 0.261**
- **hybrid vs `retry_only`: p = 0.372** ← the comparison that matters

**A confidence interval** is the range the true value plausibly sits in. **A p-value** is the
probability of seeing a gap this big by chance alone if there were really no difference. Below
0.05 is the conventional bar. We are far above it.

So we **cannot** claim hybrid beats the control. That is stated plainly in the report.

---

## 6.7 The variance floor — an accidental finding

Three configurations ended up doing **identical work** — `baseline` never repairs,
`compiler_only` had nothing to fix, `pyverilog_only` had no findings. Same code path.

They scored:

| Sweep | baseline | compiler_only | pyverilog_only | spread |
|---|---|---|---|---|
| Sonnet, our circuits | 67% | 67% | 33% | **33 points** |
| mini, our circuits | 17% | 50% | 33% | **33 points** |

**Same program. 33 points apart. Twice, independently, on different models.**

That is pure randomness from temperature 0.7. The difference we were trying to measure was
11.4 points — **about a third of the noise**.

**One caution, because an examiner may push on it.** That 33-point figure is measured at
*twelve circuits per arm*. It does not transfer unchanged to the pooled comparison, which has
forty-four. At twelve circuits and a pass rate near 0.4 the expected spread across three
identical arms is about 24 points, so 33 is a high but ordinary draw. At forty-four it is
about 12 points. We also have a direct measurement at the larger size: `baseline` and
`pyverilog_only` run identical code and differ by **6.8 points** over all 44 runs. That 6.8 is
the right number to judge the 11.4-point gap against — so the gap is roughly 1.7x the noise,
not half of it, and still not significant.

**Why this is genuinely valuable:** it says that at these sample sizes, small differences
carry no information. AutoBench's headline ablation gains are **8% and
10%**, reported from single runs without error bars. At the variance we measured, those numbers
could not support the conclusions drawn from them.

---

## 6.8 Two more findings

**Blind retry can make things worse.** On the hard benchmark circuits `retry_only` dropped
Eval0 to **70%**, against 90–95% for everything else. It broke 6 of 20 testbenches that had
compiled before the retry. A second attempt is not free — throw away a working answer and you
may draw a worse one.

**Cost against quality:**

| Mode | tokens vs baseline | Eval1 |
|---|---|---|
| `pyverilog_only` | −2% | 20.5% |
| `baseline` | — | 27.3% |
| `compiler_only` | **+6%** | **34.1%** |
| `retry_only` | +29% | 29.5% |
| `hybrid` | +50% | 40.9% |

**`compiler_only` is the efficient choice** — 7 points for 6% more tokens. `hybrid` buys the
top score at half again the cost, without statistical support.

`pyverilog_only` is *cheaper* than baseline because the error-reasoning AI call is skipped
when the report is clean — and it was always clean.

Total spend on all experiments: **≈ $9.20**.

---

## 6.9 The one-sentence summary

> We built a tool that reliably catches a kind of mistake AI models have largely stopped
> making, and we proved that carefully enough — with a validated instrument and the
> alternatives ruled out — that the finding is worth reporting.

---

**Next:** [7. Us vs AutoBench](07-comparison.md)
