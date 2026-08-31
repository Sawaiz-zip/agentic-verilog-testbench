# 5. Our Pipeline, Node by Node

Thirteen nodes. For each: what goes in, what comes out, and why it exists.

---

## 5.1 The shape of it

```
     classify  →  gen_dut  →  extract_spec  →  gen_scenarios
                                                    │
                            ┌───────────────────────┴──────────────┐
                            ▼                                      ▼
                       gen_driver                            gen_checker
                            └───────────────┬──────────────────────┘
                                            ▼
                                    merge_generation
                                            ▼
                            standardise  (sequential circuits only)
                                            ▼
                                  pyverilog_analysis     ← our contribution
                                            ▼
                                     error_reasoner
                                            ▼
                              repair  /  regenerate
                                            ▼
                                        evaluate   (Eval0 / Eval1 / Eval2)
```

**Input:** a plain-English description of a circuit.
**Output:** a Verilog testbench, a Python checker, and a complete record of what happened.

---

## 5.2 The generation stages

### `classify` — is it combinational or sequential?

**In:** the description. **Out:** `"CMB"` or `"SEQ"`. **Model:** the cheap one.

Everything downstream branches on this. Sequential circuits need a clock generated, need
outputs watched over time, and get an extra standardisation step.

*Why the cheap model?* It is a two-way classification from a paragraph of English. Paying for
the strong model here would be waste.

### `gen_dut` — write the circuit

**In:** the description. **Out:** Verilog for the circuit. **Model:** strong.

**This is where we differ from AutoBench.** They never generate the DUT; we do.

*Why?* Two reasons.

1. **It is the realistic flow.** In practice you have a description, you produce a design, then
   you test it. Testing a design that was handed to you pre-verified is not the normal case.
2. **It keeps the evaluation honest.** If the AI could see the correct circuit while writing
   the testbench, it could copy the answer. The golden circuit is used *only* at marking time.

Each run records `eval_dut_source` — `"golden"` or `"generated"` — so it is always clear what
a run was scored against.

### `extract_spec` — structure the description

**In:** the description and the generated circuit. **Out:** JSON listing ports, behaviour,
timing. **Model:** strong.

Later stages read this structured summary rather than re-reading English prose. Same idea as
AutoBench's Stage 1.

### `gen_scenarios` — invent the test cases

**In:** the spec. **Out:** a list of named scenarios. **Model:** cheap.

Something like: `reset_clears_counter`, `wraps_at_maximum`, `holds_when_disabled`.

Naming them matters — the names appear in the output as `PASS: reset_clears_counter`, which
is how we later attribute failures to specific behaviours.

### `gen_driver` and `gen_checker` — run in parallel

**`gen_driver`** writes the Verilog testbench. **Model:** strong. This is the main artefact.

**`gen_checker`** writes a Python checker. **Model:** strong.

They run as **parallel branches** because neither needs the other's output. LangGraph handles
this; it saves wall-clock time.

### `merge_generation` — the barrier

Does nothing. Exists so the next routing decision waits for **both** branches to finish rather
than racing them. In graph terms it is a fan-in barrier.

---

## 5.3 `standardise` — the deterministic fix (sequential only)

**In:** the testbench and the spec. **Out:** the testbench, possibly with lines inserted.
**Model:** none. This is plain Python.

**What it does.** Two things:

1. If a circuit output is never observed anywhere, insert a `$monitor` that prints it
2. If a clock is declared but never toggled, insert a clock generator

**Why Python and not an AI?** Inserting a monitor statement is mechanical — there is one
correct answer. Using a model would be slower, cost tokens, and could refuse in ways that are
tedious to detect.

> **This is the direct equivalent of AutoBench's code standardisation** — their largest single
> improvement (sequential Eval0 55% → 97%). Theirs is partly LLM-driven; ours is not.

**Three safety properties:**

- **Idempotent** — it marks its own output with `// [standardised]` and does nothing on a
  second pass
- **Fail-safe** — if anything goes wrong it returns the input unchanged, because a missing
  monitor is better than a corrupted testbench
- **Never touches the circuit**, only the testbench

**How much did it do in practice?** Almost nothing — modern models already observe their
outputs. Same story as our static checks (doc 6).

---

## 5.4 `pyverilog_analysis` — the static localiser

**In:** the testbench and the circuit. **Out:** a structured report. **Model:** none.

**This is the project's contribution.** It parses both files into an AST and runs six checks.

| Check | Catches | Could the compiler see it? | Could the simulator? |
|---|---|---|---|
| `port_binding_mismatch` | port bound under a wrong name, or a port left unconnected | partly | usually |
| `width_mismatch` | signal width ≠ port width | **no** (warning only) | sometimes |
| `undriven_input` | a circuit input never assigned | no | usually |
| `unobserved_output` | an output never checked or printed | no | **no** |
| `missing_fdisplay` | sequential output never made observable | no | **no** |
| `clock_never_toggled` | clock set once, never toggled | no | rarely |

**The two rows in bold carry the argument.** An unchecked output cannot be caught by running
the testbench, because the testbench *passes* — it is not looking. Static analysis is the only
option.

**A seventh check was deleted.** `sensitivity_list_error` looked for edge-triggered `always`
blocks in the testbench. AI testbenches do not use that style (they use `@(posedge clk)` inside
`initial`), so it caught **0 of 5** injected faults and produced a false alarm on a *correct*
testbench. We removed it rather than repair it — a check with no recall and false alarms is
worse than no check, because it wastes the repair budget.

### The bug worth telling your professor about

Several checks ask "does this signal appear in a comparison or a print?" Asked of raw text,
**comments and string literals answer that question with text that is not code**:

```verilog
$display("PASS: addition_boundary_overflow");   // the word "overflow" is in here
```

That made the `overflow` output *look* checked when the testbench had stopped checking it.
Detection for that fault class went from **47% to 100%** once we blanked strings and comments
before searching. It is a false *negative* — it hides real bugs — and nothing in the ordinary
test suite caught it. The fault-injection study did.

---

## 5.5 `error_reasoner` — turn findings into instructions

**In:** the analysis report. **Out:** a structured error list. **Model:** strong.

Converts a machine report into something a model can act on: which signal, what is wrong, what
to do.

**It skips the AI call entirely when the report is clean**, which saves tokens. In our
experiments the report was almost always clean, which is why `pyverilog_only` ended up
*cheaper* than baseline.

---

## 5.6 `repair` and `regenerate` — two kinds of second attempt

### `repair`

**In:** the testbench plus an error report. **Out:** a new testbench. **Model:** strong.

Three things can trigger it:

1. **static** — the analyser found something
2. **compile** — `iverilog` refused it
3. **simulation** — scenarios failed against the golden circuit

Bounded at **3 iterations**, with two safety mechanisms:

- **Oscillation detection** — if the same error comes back, or the regenerated testbench is
  byte-identical to the last one, stop. Another identical attempt will not help.
- **Best-so-far retention** — the repair rewrites the *whole* testbench, so attempt 3 can be
  worse than attempt 1. We keep the best-scoring version, not the most recent. Without this, a
  configuration that repairs more could score *worse* than one that repairs less, which is not
  a property an experiment should have.

### `regenerate` — the control

**In:** nothing but the original prompt. **Out:** a fresh testbench. **Model:** strong.

It is given **no error report, no findings, no simulator output**. It is deliberately blind.

**Why this node exists** is the most important methodological point in the project — see
§5.8.

---

## 5.7 `evaluate` — the marking

**In:** the testbench and the golden circuit. **Out:** Eval0, Eval1, Eval2 and telemetry.
**Model:** the cheap one, for generating mutants.

1. **Eval0** — compile with `iverilog`. Fail here and stop.
2. **Eval1** — run with `vvp`. Any `FAIL:` in the output means the testbench is wrong.
3. **Eval2** — generate 5 mutants, run the testbench against each, count how many it catches.

Everything is written to `results/<run_id>.json`: both artefacts, all AI calls with tokens and
latency, the static findings from every pass, the mutants themselves, and the repair history.

---

## 5.8 The five configurations — and why `retry_only` matters

The same thirteen nodes, five different rules about when repair is allowed.

| Mode | Repairs when |
|---|---|
| `baseline` | never |
| `retry_only` | never — **but regenerates once anyway, told nothing** |
| `compiler_only` | compilation fails |
| `pyverilog_only` | static analysis finds something |
| `hybrid` | any of the three |

### The confound `retry_only` removes

Suppose `hybrid` beats `baseline`. Two explanations fit:

1. The feedback identified the problem and guided the fix
2. The model just got **a second try**, and trying twice sometimes works better

You cannot tell these apart by comparing to `baseline`, because **`baseline` never gets a
second try**.

`retry_only` gets the second try with **zero information**. So:

> **A configuration must beat `retry_only`, not merely `baseline`, before its feedback can be
> credited with the improvement.**

**AutoBench has no such arm.** Their +8% and +10% cannot separate these two explanations.
This is our clearest methodological improvement over the paper we build on.

*(And when we ran it: `hybrid` 40.9% vs `retry_only` 29.5%, p = 0.372 — not significant. So we
report that honestly rather than claiming a 14-point win over baseline.)*

---

## 5.9 Why a graph rather than a script

A script would work fine until the repair loop is added. Once a later step can jump back to an
earlier one, the conditions controlling that jump get scattered through the code.

With a graph, every jump is a small named function:

```python
def should_repair(state, mode) -> str:
    if mode is BASELINE:            return "evaluate"
    if not state["error_report"]:   return "evaluate"
    return "repair"
```

**The research payoff:** our five configurations differ *only* in what three such functions
return. The nodes are byte-identical. That means we could **verify** the five arms are
genuinely distinct by evaluating those functions over a matrix of states — instead of hoping
they were. That is a real methodological benefit, not just tidier code.

---

## 5.10 Engineering practices worth mentioning

- **Prompts are files**, not strings — nine Jinja templates in `prompts/`, so they can be
  diffed, reviewed, and **frozen at a tagged commit** before experiments
- **Every AI call is logged** — node, model, tokens in/out, latency, temperature. The entire
  cost analysis comes from these records
- **201 tests, all offline**, spending zero tokens. Several of our worst bugs were caught only
  because running the full suite was cheap enough to do after every change
- **The harness aborts cleanly** if the API runs out of credit or hits a daily quota, rather
  than failing 100 runs one at a time

---

**Next:** [6. Our Experiments and Results](06-experiments-and-results.md)
