# Results Walkthrough — LLM-Driven Verilog Testbench Generation

**S6.ReKI.1** · Muhammad Sawaiz Naveed · TU Ilmenau

This document explains the results of my first full ablation run. I ran **8 circuits**
through the pipeline in **4 repair modes** each (32 runs), at the sampling
temperature of **0.7**. Below I first give the big picture — every circuit, its
description, and how it performed — then I walk through a single circuit node by node
to show exactly what each stage received and produced, and finally I read off the
metrics.

---

## 1. What I am measuring

The pipeline takes a **plain-English circuit description**, generates its own design
(DUT), then generates and grades a Verilog testbench for it. Three progressively
stricter checks (there is no Eval3):

| Metric | Question | Tool |
|---|---|---|
| **Eval0** | Does the testbench **compile**? | Icarus Verilog (`iverilog`) |
| **Eval1** | Does it **pass against the correct design** (no false failures)? | simulation (`vvp`) |
| **Eval2** | Does it **catch bugs** — reject mutated, broken designs? | simulation vs mutants |

The four **modes** differ only in *when the LLM is allowed to repair its testbench*:

- **baseline** — one shot, no repair.
- **compiler_only** — repair only if compilation fails.
- **pyverilog_only** — repair only if my Pyverilog static analysis finds a structural error (**this is the core contribution**).
- **hybrid** — static analysis first, then compiler/simulator (both feedback sources).

---

## 2. The 8 circuits and how each performed

For each circuit I report all three metrics. I show them for the three key modes as
`baseline → pyverilog_only → hybrid` so the effect of adding static analysis, then
simulation feedback, is visible left to right.

- **Eval0** = compiles. **Eval1** = passes the correct design (`P`/`F`).
- **Eval2** = fraction of injected mutant bugs the testbench catches (`1.0` = all).

| # | Circuit | Type | What it does | Eval0 | Eval1 (base→pyv→hyb) | Eval2 (base→pyv→hyb) |
|---|---|---|---|---|---|---|
| 1 | `half_adder` | CMB | `sum = a⊕b`, `cout = a·b` | ✓ | P → P → P | 1.0 → 1.0 → 1.0 |
| 2 | `mux2to1` | CMB | `out = sel ? b : a` | ✓ | P → P → P | 1.0 → 1.0 → 1.0 |
| 3 | `alu_1bit` | CMB | 1-bit ALU: AND/OR/XOR/NOT by 2-bit `op` | ✓ | P → P → P | 1.0 → 1.0 → 1.0 |
| 4 | `comparator_2bit` | CMB | compares two 2-bit numbers → `eq/lt/gt` | ✓ | P → P → P | 1.0 → 1.0 → 1.0 |
| 5 | `priority_encoder` | CMB | index of lowest set bit of 4-bit input + `valid` | ✓ | P → P → P | 1.0 → 1.0 → 1.0 |
| 6 | `dff` | **SEQ** | D flip-flop: `q <= d` on `posedge clk` | ✓ | **F → P → P** | **0.0 → 1.0 → 1.0** |
| 7 | `counter_4bit` | **SEQ** | synchronous 4-bit up-counter with reset | ✓ | **F → F → P** | **0.0 → 0.0 → 1.0** |
| 8 | `shift_register` | **SEQ** | 4-bit serial-in / parallel-out shift register | ✓ | P → P → P | **0.8 → 0.8 → 1.0** |
| | **Totals** | | | **8/8 compile** | **6/8 → 7/8 → 8/8** | avg **0.72 → 0.80 → 1.0** |

Repairs were needed only on the sequential circuits: `dff` (1), `counter_4bit` (1 in
hybrid), `shift_register` (1 in pyverilog_only, 2 in hybrid). Everything else passed
first try.

What this table shows:

1. **Eval0 = 100% everywhere** — every generated testbench compiles, in every mode.
2. **All 5 combinational circuits pass Eval1 *and* catch every bug (Eval2 = 1.0) in
   every mode, with zero repairs.** The combinational pipeline is solid.
3. **The sequential circuits are where the modes separate** — the hard case (the
   paper we build on scored only 26% here).
4. **Static analysis alone lifts Eval1 from 75% → 88%** (`dff` flips F → P once
   Pyverilog catches its structural bug and the LLM repairs it) — improvement
   **before any simulation runs**. This is the headline result.
5. **hybrid reaches 100% on both Eval1 and Eval2.** Two things only it catches:
   `counter_4bit`, a *behavioural* bug invisible to static analysis (needs
   simulation); and `shift_register`, which *passed* Eval1 in the other modes yet
   caught only **80%** of mutants — a reminder that passing Eval1 is not enough, and
   the extra repairs pushed its bug-catching to 100%.

---

## 3. One circuit, node by node — `dff`

I pick `dff` because it is the clearest demonstration of the whole pipeline: in
`baseline` it **fails**, but in `pyverilog_only` the static analyser catches a real
structural bug and the LLM repairs it into a **pass**. Same model, same temperature —
the only difference is the static-analysis repair.

> **Description given to the pipeline (the only input):**
> *"Implement a module named `dff` — a positive-edge-triggered D flip-flop. Inputs
> `clk`, `d`; output `q`. On every rising edge of `clk`, `q` takes the value of `d`;
> `q` holds between edges. This is a sequential circuit."*

| Node | Input it received | Output it produced | Correct? |
|---|---|---|---|
| **1. Classify** | the description | `circuit_type = SEQ` | ✅ It is clocked → SEQ. |
| **2. Generate DUT** | description + `SEQ` | `always @(posedge clk) q <= d;` | ✅ Correct flip-flop, matches the golden design. |
| **3. Extract spec** | description + **generated DUT** | ports `clk`,`d` (in), `q` (out); clocked | ✅ Ports and timing right. |
| **4. Generate scenarios** | the spec | reset-to-known-state, `d=0→q=0`, `d=1→q=1`, hold-across-edges | ✅ Covers the behaviour. |
| **5a. Generate driver** | spec + scenarios | first-attempt testbench — **but missing the `$display` that observes `q`** | ❌ **The bug.** It drives the clock and `d`, but never actually prints/checks the output — so it silently tests nothing. This is exactly why `baseline` fails. |
| **5b. Generate checker** | spec + scenarios | Python pass/fail parser (runs parallel to 5a) | ✅ |
| **6. Standardise** | the testbench | (SEQ housekeeping pass) | ✅ |
| **7. Pyverilog analysis** | **generated testbench + generated DUT** | flags `missing_fdisplay` — output `q` is never observed | ✅ **The catch.** Found deterministically, in milliseconds, **before any simulation.** |
| **8. Error reasoner** | the Pyverilog finding | "output `q` is never observed — add a `$display` after each clocked check" | ✅ Turns the raw finding into an actionable fix. |
| **9. Repair** → back to 7 | spec + scenarios + **the error report** | regenerated testbench that now prints `q` on every check (`repair_iter = 1`) | ✅ Second Pyverilog pass is clean → loop exits. |
| **10. Evaluate** | testbench + **golden DUT** + mutants | **Eval0 ✅, Eval1 ✅ (9/9 scenarios), Eval2 = 1.0** | ✅ `final_status: success`. |

**Result on `dff`:** `baseline` = FAIL, `pyverilog_only` = PASS after one static
repair. That single controlled comparison is the core contribution in miniature.

### Where the generated DUT is used, and where it isn't

There are two designs in play, and it matters which is used where:

- **Generated DUT** (produced by node 2) is the "design under test" the pipeline
  works with. It is used by **node 3 (spec), node 5a (driver ports), and node 7
  (Pyverilog analysis)**.
- **Golden DUT** (the known-correct reference) is used **only at node 10
  (evaluate)** — purely for grading Eval0/1/2. It never influences generation.
- **Node 1 (classify)** uses **neither** design — it runs on the description alone,
  before any DUT exists.

So the generation and static-analysis half of the pipeline runs entirely on the
model's *own* generated design; the golden reference only comes in at the very end to
score the result fairly.

---

## 4. A second circuit, node by node — `counter_4bit` (the *hybrid* case)

`dff` was fixed by static analysis. `counter_4bit` is the opposite lesson: its bug is
**behavioural, not structural**, so Pyverilog cannot see it — and it is fixed only by
**hybrid**, using simulation feedback. This is why the two feedback layers exist.

Look at the modes for this circuit: `baseline` **F**, `pyverilog_only` **F**,
`hybrid` **P (1 repair)**. Note that `pyverilog_only` failed with **zero repairs** —
the static analyser looked at the testbench, found nothing wrong structurally, and
let it through; it still failed Eval1.

> **Description given to the pipeline:** *"A synchronous 4-bit up-counter with
> synchronous reset. Inputs `clk`, `rst`; output `out` (4 bits). On each rising edge:
> if `rst`, `out ← 0`; else `out ← out + 1` (wrapping 15 → 0)."*

| Node | Input it received | Output it produced | Correct? |
|---|---|---|---|
| **1. Classify** | the description | `circuit_type = SEQ` | ✅ Clocked → SEQ. |
| **2. Generate DUT** | description + `SEQ` | `always @(posedge clk) out <= rst ? 0 : out+1;` | ✅ Correct synchronous counter, matches golden. |
| **3. Extract spec** | description + **generated DUT** | ports `clk`,`rst` (in), `out[3:0]` (out); clocked | ✅ |
| **4. Generate scenarios** | the spec | 11 scenarios: initial state, increment steps, reset, **wrap-around (15→0)**, reset-mid-count, long sequences | ✅ Good coverage — including the tricky timing cases. |
| **5a. Generate driver** | spec + scenarios | first-attempt testbench that is **structurally clean but has the wrong expected values** for the hard timing scenarios | ❌ **The bug.** Ports, clock and output prints are all present — but the testbench expects the wrong counter value at some cycles (wrap-around, reset-mid-count). A *behavioural* error, not a structural one. |
| **6. Standardise** | the testbench | SEQ housekeeping pass | ✅ |
| **7. Pyverilog analysis** | testbench + generated DUT | **clean report — no structural errors** | ⚠️ Correct *as far as structure goes*: every port is bound, the output is observed, the clock is driven. But static analysis **cannot judge whether the expected values are right**, so it is blind to this bug. |
| **8. Error reasoner** | the (empty) report | no errors | This is where `pyverilog_only` stops — nothing to repair, so it proceeds straight to evaluation and **fails Eval1**. |
| **10. Evaluate (1st pass)** | testbench + **golden DUT** | **Eval1 FAILS** — the log shows `PASS: initial_state … PASS: reset_counter`, then `FAIL: wrap_around`, `FAIL: assert_reset_mid_count`, `FAIL: multiple_clock_cycles_no_reset`, `FAIL: long_sequence_with_reset` | ✅ Running the simulation against the correct design **exposes exactly which expected values were wrong**. |
| **9. Repair (simulation feedback)** — *hybrid only* | spec + scenarios + **the failing simulation log** | in `hybrid`, the failed Eval1 re-enters the repair loop with the simulation output as feedback; the LLM regenerates the testbench with corrected expected values (`repair_iter = 1`, `feedback_source = simulation`, 3895 tokens in / 1852 out) | ✅ |
| **10. Evaluate (2nd pass)** | repaired testbench + golden DUT + mutants | **Eval0 ✅, Eval1 ✅ (11/11 scenarios), Eval2 = 1.0** | ✅ `final_status: success`. |

**Result on `counter_4bit`:** `baseline` and `pyverilog_only` both FAIL; only `hybrid`
passes, because only `hybrid` runs the simulation, sees the specific scenario
mismatches, and feeds them back for repair.

### Why this differs from `dff`

Both circuits produced a broken first testbench, but the bugs are different in kind:

| | `dff` | `counter_4bit` |
|---|---|---|
| Bug type | **Structural** — output never observed (`missing_fdisplay`) | **Behavioural** — output observed, but wrong expected values |
| Caught by Pyverilog? | ✅ Yes (before simulation) | ❌ No (report is clean) |
| Fixed by | **pyverilog_only** (static repair) | **hybrid** only (simulation-feedback repair) |

This is the core argument for the layered design: **Pyverilog catches structural bugs
cheaply, before simulation; the simulator then catches the behavioural bugs static
analysis is blind to.** `hybrid` runs both, in that order, which is why it is the only
mode that reaches 100%.

---

## 5. The numbers

| Mode | Eval1 pass rate | Notes |
|---|---|---|
| baseline | 6/8 = **75%** | no repair; the 2 SEQ failures are genuine testbench bugs |
| compiler_only | 6/8 = **75%** | compiler feedback fixes some, breaks even overall |
| **pyverilog_only** (ours) | 7/8 = **88%** | **static analysis alone beats baseline** — the key finding |
| **hybrid** | 8/8 = **100%** | static + simulation feedback; best observed |

- **Eval0 = 100%** across all modes (the seed paper, AutoBench, reported 95.7%).
- **Eval2:** hybrid catches **all** injected bugs (average 1.0). The weaker modes
  average ~0.72–0.80 — not just because some testbenches fail Eval1, but because a
  testbench can *pass* Eval1 and still miss bugs (`shift_register` caught only 80% of
  mutants until the extra repairs).
- **Repairs are rare and cheap:** only 3 of 8 circuits ever needed a repair, all
  sequential, all resolved in 1–2 iterations.

**One honest nuance.** Static analysis catches *structural* bugs (missing output
observers, wrong ports, undriven inputs, width mismatches) — that is why
`pyverilog_only` lifts the pass rate. It does **not** catch deep *behavioural* bugs:
`counter_4bit` had a wrong expected count sequence, which only shows up when you
actually run the simulation — so only `hybrid` fixed it. This is by design: Pyverilog
first (cheap, catches structural errors early), simulator second (catches the rest).

---

## 6. Caveats I am carrying forward

- **8 circuits is a small sample** — these results validate that the pipeline works
  and that static analysis helps; they are not yet a benchmark score.
