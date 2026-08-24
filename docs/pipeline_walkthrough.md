# Pipeline Walkthrough — Node by Node (Plain-English)

> **Purpose:** Explain what every node in the LangGraph pipeline does and what
> output it produces. Grounded in a **real run** (`alu_1bit`, baseline mode) from
> the OpenRouter ablation sweep (Claude Sonnet 4.5 + gpt-4o-mini) so every claim is
> tied to actual output.
>
> Companion to `CLAUDE.md` (§6 architecture), `docs/results_walkthrough.md`
> (the actual results), and `docs/architecture_decisions.md` (why each choice).

---

## 1. The big picture

The pipeline takes **a plain-English description of a chip** and produces **a
Verilog testbench** (a program that checks whether that chip works). Then it
grades itself.

Think of it as a **factory assembly line**. Each station (a "node") does one
small job and passes its work to the next station. **LangGraph** is the conveyor
belt connecting them. The whole thing is a **graph** — mostly a straight line,
but with a few forks and one loop.

```
classify → gen_dut → extract_spec → gen_scenarios
                                          │
                              ┌───────────┴───────────┐
                          gen_driver              gen_checker      ← run in parallel
                              └───────────┬───────────┘
                                    merge_generation
                                          │
                           ┌──────────────┴──────────────┐
                    (SEQ) standardise              (CMB) skip it
                                          │
                              pyverilog_analysis → error_reasoner
                                          │
                                   [repair loop?] ←──────┐
                                          │              │
                                      evaluate ──────────┘
                                          │
                                        DONE
```

**Model routing:** cheap model (gpt-4o-mini) for easy jobs, strong model
(Claude Sonnet) for code and reasoning. This keeps cost down without hurting
the parts that matter.

---

## 2. Every node, in plain language

Format: **what it does** → **what it produced in the real `alu_1bit` run**.

### 1. `classify` — "Is this a clock-based circuit or not?"
Reads the description and decides: **CMB** (combinational — output depends only
on current inputs, like a calculator) or **SEQ** (sequential — has memory/a
clock, like a counter). Uses the **cheap** model because it's an easy yes/no.
→ **Result:** `circuit_type: "CMB"`. Cost: 303 tokens in, just **9 tokens out**
(basically one word). This is why cheap-model routing matters.

### 2. `gen_dut` — "Build the chip we're going to test"
The **DUT = Device Under Test**. The pipeline generates the actual Verilog chip
from the description (using the **strong** model). This is what the testbench
will be pointed at.
→ **Result** (`dut_rtl`): a real 1-bit ALU module —
```verilog
assign result = (op == 2'b00) ? (a & b) :
                (op == 2'b01) ? (a | b) :
                (op == 2'b10) ? (a ^ b) : ~a;
```
Correct ALU, written in 111 output tokens.

### 3. `extract_spec` — "Turn the prose into a structured checklist"
Converts the fuzzy description into a clean **JSON spec**: exact port names,
bit-widths, behavior rules. This structure is what makes later nodes reliable —
they read fields, not English.
→ **Result:** a `spec` dict (ports: a, b, op[1:0], result; the 4 operations).
333 output tokens.

### 4. `gen_scenarios` — "List the test cases we should try"
Produces a named list of **test scenarios** — specific input combinations and
the expected output for each. Cheap model, because it's just enumerating cases.
→ **Result:** 11 scenarios like `AND_0_0`, `OR_1_0`, `XOR_1_1`, `NOT_1`. These
names show up later in the scorecard.

### — Here the line FORKS into two parallel branches —

### 5a. `gen_driver` — "Write the Verilog testbench" (the *driver* track)
The star output. Writes the actual **testbench**: sets inputs, waits, checks
outputs, prints `PASS`/`FAIL`. Strong model.
→ **Result** (`driver_rtl`): a full `tb_alu_1bit` module that instantiates the
DUT and runs all 11 scenarios, e.g.:
```verilog
a = 1; b = 1; op = 0;   // AND_1_1
#10;
if (result === 1) $display("PASS: AND_1_1");
else              $display("FAIL: AND_1_1");
```

### 5b. `gen_checker` — "Write a Python grader" (the *checker* track)
In parallel, a Python script that reads simulation output and decides pass/fail.
Running these two in parallel is deliberate (cuts wall-clock time) — LangGraph
forks automatically because `gen_scenarios` has two outgoing edges.

### 6. `merge_generation` — "Wait for both branches"
A **barrier**. Does no real work; it just makes sure *both* driver and checker
are finished before moving on. Without it, the next decision could act on a
half-built testbench.

### 7. `standardise` — SEQ only, and this is a KEY project contribution
For sequential circuits, LLMs often forget to print signal values or toggle the
clock. This node is a **deterministic Python fixer** (no LLM) that inserts a
`$monitor` and a clock toggle if missing. **CMB circuits skip this entirely** —
which `alu_1bit` did. It fires on `dff`, `counter_4bit`, `shift_register`.

> This replaces AutoBench's fragile LLM-based `$fdisplay` insertion with a
> deterministic parser — see `CLAUDE.md` §9 contribution #3.

### 8. `pyverilog_analysis` — "Static inspection, no running" (research core, RQ2)
The heart of the project. Parses the testbench with **Pyverilog** and checks for
errors *without simulating* — much faster than a full simulation:
- Do the testbench's port connections match the DUT's ports?
- Any DUT inputs left undriven? Any outputs never checked?
- (SEQ) Is there a `$fdisplay`/`$monitor` for every output?
→ **Result:** a `pyverilog_report`. For `alu_1bit` it was clean.

### 9. `error_reasoner` — "Explain the errors in LLM-friendly terms"
If Pyverilog found problems, the strong model turns raw findings into structured
fixes (`{type, signal, line, suggested_fix}`). **Cost-saver:** if the report is
clean, it skips the LLM entirely.
→ In the `alu_1bit` run there is **no `error_reasoner` entry** in `llm_calls` —
nothing was wrong, so zero tokens spent.

### 10. `repair` — "Fix and retry" (the loop, RQ3)
If errors exist *and* the ablation mode allows repairing, it re-generates the
testbench with the error feedback, then loops back through analysis. Bounded to
**3 iterations**, with **oscillation detection** (if it keeps making the same
mistake, stop). Because each repair regenerates the whole testbench, the pipeline
keeps a **best-so-far snapshot** and reports the highest-scoring iteration, not the
last one — so more repair can never score *below* less repair.
→ `alu_1bit` baseline needed **0 repairs** (`repair_iter: 0`).

### 11. `evaluate` — "The final exam" (the three grades)
Compiles and runs everything with **Icarus Verilog**. This is the **only** node
that uses the *golden* DUT (the known-correct reference) — every earlier node worked
with the pipeline's own **generated** DUT. The golden DUT is used purely for grading:
- **Eval0** — does it compile? → `true`
- **Eval1** — does the testbench pass against the correct (golden) DUT? → `true`
- **Eval2** — does it *catch bugs*? Makes broken "mutant" chips and checks the
  testbench flags them. → `eval2_pass_rate: 1.0` (caught 100%). The `gen_mutant`
  calls in the log are those broken chips being created.
→ **Final:** `final_status: "success"`, 11/11 scenarios passed.

---

## 3. How to read a result JSON

Every run writes one JSON file. The fields that matter most:

| Field | Meaning |
|---|---|
| `final_status` | The verdict: `success` / `oscillated` / `exhausted_iters` / `failed_*` |
| `eval0_pass` / `eval1_pass` / `eval2_pass_rate` | The three grades (compiles / correct / catches bugs) |
| `repair_iter` + `repair_history` | How many fix-attempts, and why each was triggered |
| `failure_stage` | *Which node* broke, if it failed (per-node attribution contribution) |
| `llm_calls` | Every model call: node, model, tokens, latency — the cost data |
| `tokens_in_total` / `tokens_out_total` | Total cost for the run |

---

## 4. The 4 ablation modes (why each fixture runs 4×)

The whole experiment compares **repair strategies**. Same modules, four setups:

| Mode | Repairs when… | Purpose |
|---|---|---|
| **baseline** | never | how good is the raw LLM alone? |
| **compiler_only** | code won't compile | AutoBench-style feedback |
| **pyverilog_only** | our static analyzer flags it | *our* contribution alone |
| **hybrid** | any of the above | the full system |

Comparing these four answers the research questions: does Pyverilog static
analysis actually help, and is it worth the cost (RQ3 / RQ4)?

---

## 5. Model routing summary

| Node | Model | Why |
|---|---|---|
| `classify` | cheap | one-word yes/no |
| `gen_scenarios` | cheap | enumerate cases |
| `gen_mutant` | cheap | small mechanical edits |
| `gen_dut` | strong | must be correct Verilog |
| `extract_spec` | strong | structure matters |
| `gen_driver` | strong | the main artifact |
| `gen_checker` | strong | grading logic |
| `error_reasoner` | strong | reasoning (only when needed) |
| `repair` | strong | regenerate under constraints |
| `standardise` | **none** | deterministic Python, no LLM |
| `pyverilog_analysis` | **none** | deterministic static analysis |
| `merge_generation` | **none** | barrier only |
