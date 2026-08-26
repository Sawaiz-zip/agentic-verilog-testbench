# 4. The AutoBench Paper

**Full title:** *AutoBench: Automatic Testbench Generation and Evaluation Using LLMs for HDL
Design*
**Authors:** Ruidi Qiu, Grace Li Zhang, Rolf Drechsler, Ulf Schlichtmann, Bing Li
**Venue:** MLCAD 2024 · arXiv:2407.03891
**Institutions:** TU Munich, TU Darmstadt, Bremen, Siegen

This is the paper our project builds on. You must be able to explain what they did, what
they got, and where we differ.

---

## 4.1 The problem they identified

If you ask an LLM "write me a testbench for this circuit" in one go, the result is usually
poor. Their baseline — direct one-shot generation — passed only about **28%** of the time.

Their diagnosis: writing a testbench is several different tasks at once (understand the
circuit, invent test cases, write Verilog, write checking logic), and asking for all of them
in one call gets none of them done well.

**Their solution: split it into stages.** This is chain-of-thought reasoning applied to code
generation.

---

## 4.2 Their pipeline, stage by stage

Their input is **the circuit description and the module header** — the port list. Note what
is *not* included:

> "In generating a testbench, the DUT is not available to AutoBench. Otherwise, errors in the
> DUT may misguide the LLMs so that the resulting testbench may ignore errors."

The AI never sees the correct circuit while writing the test. Same principle as not giving a
student the answer key.

| Stage | What the LLM is asked to produce |
|---|---|
| **Stage 0** | Is this circuit combinational or sequential? |
| **Stage 1** | A structured specification: ports, behaviour, timing |
| **Stage 2** | A list of named test scenarios |
| **Stage 3** | Core checking rules, in Python |
| **Stage 4** | The Verilog **TB-Driver** |
| **Stage 5** | The Python **TB-Checker** |

### How Stage 0 works (a nice trick)

They do not have the circuit, so they cannot look for `posedge` in it. Instead they ask the
LLM to write a *sample* implementation from the description, then run a regular expression
over that sample looking for `always @(posedge ...)`. If found, the circuit is sequential.

They justify knowing this early:

> "testbenches for sequential circuits require stringent time-dependent functions, while a
> checker for a combinational circuit can be a direct function of the current input"

**We do the same thing** — our `classify` node — but we then go further and generate the
circuit itself.

### The "hybrid testbench" — their key structural idea

Their testbench is **two files in two languages**:

- **TB-Driver** (`.v`) — Verilog. Drives the inputs and *prints* the results to a file
  called `TBout.txt`. It does not decide pass or fail.
- **TB-Checker** (`.py`) — Python. Reads `TBout.txt` and decides which scenarios failed.

**Why split it?** Their argument is that LLMs are much better at Python than at Verilog,
because there is far more Python in the training data. So they put as much of the *thinking*
as possible in Python and keep the Verilog to simple stimulus and printing.

> **This is why `$fdisplay` matters so much to them.** If the driver does not print a signal
> to `TBout.txt`, the Python checker cannot see it, and the whole check silently disappears.
> Their standardisation script exists to guarantee those prints are present.

**We chose differently.** Our testbenches are self-checking Verilog — they print `PASS:` or
`FAIL:` directly. It is simpler and avoids a second language, but it means our testbenches use
`if (out === expected)` rather than `$fdisplay`, which turned out to matter for our checks
(doc 6).

### Stage 4 is split again for sequential circuits

Writing a clocked driver is hard, so they do it in two sub-steps: first the architecture
(clock generation, reset sequence, timing), then insert the `$fdisplay` statements.

---

## 4.3 Their three self-enhancement mechanisms

After generation, three mechanisms try to fix problems. **None of them parses the Verilog** —
remember this, it is our gap.

### 1. Scenario checking

A Python script checks that every scenario named in Stage 2 actually appears in the generated
driver. If one is missing, regenerate — up to 3 attempts.

This is a **text search**, not analysis. It confirms a name is present; it says nothing about
whether the scenario is correctly implemented.

**Reported gain:** ~10% on Eval2 pass@1.

### 2. Auto-debug

If the testbench fails to compile, feed the compiler error plus the line-numbered source back
to the LLM and ask for a fix. **One attempt.**

**Reported gain:** ~8% Eval2 pass@1, and ~21% on Eval0.

> This is exactly our `compiler_only` configuration.

### 3. Code standardisation

A script that forcibly inserts missing `$fdisplay` statements for sequential circuits.

**This is their biggest single win.** Sequential Eval0 went from **55.47% → 97.33%**.

> **Remember this number — 55 to 97.** It is central to our comparison. It is a *mechanical,
> pre-simulation fix* — exactly the same category as our project's contribution.

### Reboot

If debugging fails, throw away Stages 4/5 and regenerate from scratch. Up to 5 total attempts.

---

## 4.4 Their evaluation framework: AutoEval

They introduced the Eval0/1/2 scheme described in doc 2. Their Eval2 uses **mutants** made by
an LLM from the golden RTL, and a testbench passes Eval2 if it catches **≥80%** of them.

---

## 4.5 Their results

Model: **GPT-4-turbo**, and only that one. Dataset: **156 VerilogEval problems** (81
combinational, 75 sequential).

### Eval2 pass@1 — the headline

| Group | AutoBench | Baseline | Improvement |
|---|---|---|---|
| **Total** (156) | **44.81%** | 28.46% | +57% |
| Combinational (81) | 62.22% | 47.65% | +31% |
| **Sequential (75)** | **26.00%** | 7.73% | **3.36×** |

### Eval0 pass@1 — compilation

| Group | AutoBench | Baseline |
|---|---|---|
| Total | **95.71%** | 70.06% |
| Sequential | **97.33%** | 55.47% |

### What these tell you

1. **Sequential circuits are much harder.** 26% vs 62%. Everyone struggles with clocks and
   timing. Our results agree.
2. **Their biggest relative win is on sequential** — 3.36× the baseline.
3. **Most of the Eval0 gain is from the deterministic script**, not from the LLM parts.

---

## 4.6 Limitations they acknowledge, and one they do not

**Acknowledged:** only one model tested (GPT-4-turbo), no cross-model study.

**Not acknowledged, and this is our main methodological criticism:**

Their ablation compares the full system against a version with one mechanism **disabled**. But
disabling a mechanism also removes the **regeneration attempts** that mechanism triggers.

So when they report "+8% from auto-debug", two explanations fit equally well:

1. The compiler error told the model what was wrong, and it fixed it.
2. The model simply got another attempt, and sampling twice from a random generator sometimes
   gives a better result.

**Their design cannot separate these.** There is no arm that gets an extra attempt *without*
the diagnostic information.

**That is precisely why we added `retry_only`** — a configuration that regenerates once with
no information at all. Anything must beat `retry_only`, not merely the baseline, before its
feedback can be credited. When we ran it, nothing did (p = 0.372).

---

## 4.7 How they prompt — since you asked specifically

Three things characterise their prompting:

**1. Decomposition.** Each stage is a separate call with a narrow job. Stage 2 only lists
scenarios; it does not write code.

**2. Structured intermediate outputs.** Stage 1 produces a spec in a fixed format that later
stages consume. The model is not re-reading English prose at every stage; it is reading its
own structured summary.

**3. Circuit-type-conditional guidance.** Because Stage 0 established CMB or SEQ, later prompts
give different instructions — sequential prompts emphasise timing and clocking.

**Our prompting follows the same philosophy.** Ours live as Jinja template files in
`prompts/` (nine of them), which lets us diff them, review them, and freeze them at a tagged
commit before running experiments. Ours are self-checking-Verilog oriented rather than
hybrid-testbench oriented.

---

## 4.8 What to say if asked "what is AutoBench?"

> A 2024 MLCAD paper from TU Munich that generates Verilog testbenches with an LLM by
> splitting the job into six stages instead of asking for it in one call. Their testbench is
> hybrid — a Verilog driver that prints results, and a Python checker that reads them. Three
> self-enhancement mechanisms sit on top: scenario presence checking, compiler-error
> auto-debug, and a script that inserts missing print statements. On 156 VerilogEval problems
> with GPT-4-turbo they report 44.8% Eval2 and 95.7% Eval0. Their largest single improvement
> — sequential compilation from 55% to 97% — came from the deterministic script, not the LLM.
> Nothing in their system parses the Verilog it generates, and their ablation has no control
> for the extra generation attempts each mechanism triggers.

---

**Next:** [5. Our Pipeline, Node by Node](05-our-pipeline.md)
