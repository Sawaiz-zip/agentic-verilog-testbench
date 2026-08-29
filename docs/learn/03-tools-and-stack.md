# 3. The Tools We Used

For each: what it is, why we needed it, and what it cannot do.

---

## 3.1 Icarus Verilog — the simulator

**What it is.** An open-source Verilog simulator. Free, standard, widely used in teaching and
research. Command name: `iverilog`.

**What it does.** Two steps:

```bash
iverilog -g2012 -o sim.out testbench.v circuit.v   # compile
vvp sim.out                                         # run
```

`iverilog` compiles the Verilog into an executable; `vvp` runs it. Whatever the testbench
`$display`s appears on screen.

**Why we needed it.** It is how we measure **Eval0** (does it compile?) and **Eval1** (does it
pass?). Without a simulator there is no ground truth at all.

**The critical thing it does NOT do — remember this one:**

Give it a testbench with a 3-bit wire on a 4-bit port and it prints:

```
warning: Port 3 (out) of module counter_4bit expects 4 bit(s), given 3.
       : Padding 1 high bits of the port.
```

…and then **exits successfully**. It is a *warning*, not an error. The testbench builds, runs,
and silently compares wrong values.

That single fact is a large part of why our project exists. I verified it directly rather than
assuming it, and the exact text above is quoted in the report.

---

## 3.2 Pyverilog — the static analyser

**What it is.** A Python toolkit that *reads* Verilog without running it. Written by Shinya
Takamaeda-Yamazaki, published 2015.

**What it gives you.** The main thing is an **AST** — Abstract Syntax Tree. Instead of the
file being text, it becomes a Python object tree you can walk:

```
ModuleDef "half_adder"
├── Portlist
│   ├── Input  "a"
│   ├── Input  "b"
│   └── Output "sum"
└── Assign  sum = Xor(a, b)
```

Now "which ports does this module have?" is a loop over a list, not a regex over text.

**Why we needed it.** Every one of our six checks is a question about structure:

- *Is this bound port name in the circuit's port list?* → compare AST node names
- *Do these two widths match?* → read both width nodes
- *Is this input ever assigned?* → search the testbench

Doing this with text search would be fragile. Doing it on an AST is precise.

**What it cannot do.** Three limitations we hit:

1. **It targets Verilog-2001**, with only partial SystemVerilog support.
2. **It was written for human code**, and sometimes rejects generated code.
3. **It has quirks.** One cost us an entire round of experiments: Pyverilog concatenates the
   files you give it, so a testbench ending in `endmodule` *without a trailing newline* got
   glued to the next file's `module` keyword. Every parse failed, the analysis returned an
   empty report, and **an empty report is indistinguishable from a clean one**. Our static
   analysis arm was silently identical to the baseline until we found it.

**How well did it work in the end?** 81 of 82 testbenches parsed in the first sweep, 153 of
153 in the benchmark sweep. Good enough.

---

## 3.3 Verible — the backup parser

**What it is.** Google's SystemVerilog parser and style linter.

**Why we have it.** Purely as a fallback. When Pyverilog cannot parse a file, we ask Verible
whether the file is even valid Verilog. That distinguishes "our tool is limited" from "the AI
produced garbage."

**How often was it needed?** Far more often than we first reported, and this matters.

Of the 314 analyses, Pyverilog built a syntax tree for only **190**. In **120** it failed and
we fell back to Verible; in 4 both failed. The catch: Verible only gives a syntax verdict, so
in those 120 analyses **none of the six checks ran at all** — yet the record says `parse_ok`.

| Sweep | Analyses | Pyverilog worked | Verible fallback | Both failed |
|---|---|---|---|---|
| Sonnet, our circuits | 82 | 75 | 6 | 1 |
| mini, our circuits | 79 | 51 | 25 | 3 |
| mini, VerilogEval | 153 | **64** | **89** | 0 |
| **Total** | **314** | **190** | **120** | **4** |

The failures are genuine gaps in Pyverilog's language coverage — `logic` declarations, tasks
with arguments, other SystemVerilog it does not support. They hit hardest on the big
sequential benchmark circuits, which is exactly where we most wanted the analysis to work.

> **If asked about this**, the honest answer is: "Our null result holds over the 190 analyses
> where the checks actually ran. In the other 124 the parser could not read the file, so those
> support no conclusion either way. A localiser built on a full SystemVerilog parser would
> answer RQ2 on a larger sample, and we cannot rule out that it would answer differently."

> Practical note: installing it on an Intel Mac was awkward (the official binaries are
> ARM-only and the Homebrew formula was removed); we used a conda-forge build.

---

## 3.4 LangGraph — the orchestrator

**What it is.** A Python library for building **state machines** where the steps are AI calls.

**The problem it solves.** You could write our pipeline as a normal script:

```python
circuit_type = classify(description)
dut = generate_dut(description)
spec = extract_spec(dut)
# ... and so on
```

That works fine until you add a **repair loop** — where a later step can send you back to an
earlier one. Then the conditions controlling that jump get scattered through the code, and
answering "under what circumstances does this configuration regenerate the testbench?" means
reading the whole script.

**What LangGraph gives you.** Every step is a **node**. Every transition is an **edge**. Every
conditional transition is a small named function:

```python
def should_repair(state, mode) -> str:
    if mode is BASELINE:  return "evaluate"
    if not state["error_report"]: return "evaluate"
    return "repair"
```

**Why this mattered for our research specifically.** Our five experimental configurations
differ *only* in what three such functions return. The nodes are byte-identical across all
five. That means we could **verify** the five arms are genuinely different by evaluating those
functions over a matrix of inputs — rather than hoping they were. That is a real
methodological benefit, not just tidier code.

**State** is one typed dictionary passed between nodes — 35 fields covering inputs, outputs,
loop control and telemetry.

---

## 3.5 The LLMs

We used two models through **OpenRouter** (an API that fronts many providers):

| Role | Model | Used for |
|---|---|---|
| strong | `claude-sonnet-4.5` | writing the circuit, the testbench, and repairs |
| cheap | `gpt-4o-mini` | classification, listing scenarios, making mutants |

**Why two?** Cost. Deciding "is this circuit combinational or sequential?" is easy and does
not need an expensive model. Writing correct Verilog does.

**Temperature 0.7.** Temperature controls randomness: 0 means "always give the most likely
answer", higher means more variety. We used 0.7 because it reflects realistic use.

> **This choice has a large consequence.** At 0.7 the model gives a *different answer every
> time*. We measured how different: configurations running **identical code** scored 33
> percentage points apart. That noise is bigger than any effect we were trying to detect, and
> it is one of our findings. See doc 6.

**One sweep swapped the strong model for `gpt-4o-mini`** to test whether a weaker model makes
more structural mistakes. It does not — see doc 6.

---

## 3.6 The dataset: VerilogEval

**Where it lives:** `data/verilog_eval/problems/` in our repository.

**What it is.** 156 problems from HDLBits (a Verilog practice site), packaged for evaluating
AI models. Published by NVIDIA researchers, 2023. Each problem is three files:

```
Prob153_gshare_prompt.txt   <- the natural-language description
Prob153_gshare_ref.sv       <- the correct circuit (golden DUT)
Prob153_gshare_test.sv      <- their reference testbench
```

**Why it matters.** It is the benchmark **AutoBench evaluated on**. Using it means our numbers
sit on the same ground as theirs, and it removes the objection "you picked easy circuits
yourself."

**We used 20 of the 156.** Running all of them was outside budget. The 20 were chosen by
**structural complexity, scored before any run took place** — port count, width variety,
presence of a clock. That detail matters for validity and is covered in doc 6.

> One quirk worth knowing: every VerilogEval problem names its module `RefModule`. If you
> aggregate results by module name, all 156 collapse into one row. We hit this and added a
> separate `task_id` field. Caught it before the benchmark sweeps, which was luck.

---

## 3.7 Everything else

| Tool | Role |
|---|---|
| **Python 3.11** | everything is written in it |
| **Jinja2** | prompt templates live in `prompts/*.j2` as files, not strings, so they can be diffed and frozen |
| **pytest** | 201 tests, all offline, spending zero API tokens |
| **LangSmith** | optional tracing so each AI call can be inspected |
| **Git** | version control; prompts frozen at a tagged commit before experiments |

---

## 3.8 Why each tool, in one line

If asked "why did you use X?":

- **Icarus** — we need ground truth, and it is the standard free simulator
- **Pyverilog** — we need to read Verilog structure without running it; regex would be fragile
- **Verible** — a second opinion when Pyverilog refuses a file
- **LangGraph** — a repair loop makes control flow implicit in a script; a graph keeps it explicit and testable
- **Two models** — cost; the cheap one handles the easy decisions
- **VerilogEval** — it is the benchmark the prior work used

---

**Next:** [4. The AutoBench Paper](04-autobench-explained.md)
