# 009 — Hard Circuit Fixtures (Day 2)

**Date:** 2026-08-24 · **Branch:** `009-hard-circuit-fixtures`

Day 2 of the 5-day plan in `docs/roadmap.md`. Builds the six circuits the evaluation set was
missing, and fixes a second false positive that only became visible once there were
sequential testbenches worth analysing.

## Why these circuits

`008` established that four of the five static checks are *structurally unable to fire*
on the original fixtures — 8–17 line circuits with 2–4 unambiguous ports. Each new
circuit was chosen for the check it can exercise:

| Fixture | Type | Ports | What it can trip |
|---|---|---|---|
| `alu_8bit` | CMB | 7 | `port_binding_mismatch` (7 confusable names), `width_mismatch` (8/3/1-bit mix), `undriven_input` |
| `barrel_shifter_8bit` | CMB | 5 | mixed widths (8/3/1), mode-dependent behaviour |
| `bcd_to_7seg` | CMB | 2 | differing in/out widths (4 → 7), wide truth table |
| `fsm_sequence_detector` | SEQ | 5 | multi-state tracking, `sensitivity_list_error`, exposed `state` output |
| `fifo_8x8` | SEQ | 9 | `port_binding_mismatch`, `undriven_input`, registered read, `full`/`empty`/`count` |
| `traffic_light_fsm` | SEQ | 4 | timed multi-state, exposed `timer` counter |

## Fixture validation

Compiling is not enough. **A golden DUT that contradicts its own prompt makes every
generated testbench fail Eval1 for a specification reason rather than a quality one** —
which would silently corrupt the whole ablation. So each pair was checked behaviourally:

- `alu_8bit` — 13 assertions covering all 8 ops plus carry, borrow, signed overflow and
  zero. All pass.
- `barrel_shifter_8bit` / `bcd_to_7seg` — 13 assertions covering shift modes, sign
  replication, the full decode table and invalid inputs. All pass.
- `fsm_sequence_detector` — the stream `1011011` produces exactly 2 detections, confirming
  the overlap semantics stated in the prompt.
- `fifo_8x8` — write/read ordering, `count`, and the write-while-full guard.
- `traffic_light_fsm` — the observed 8-cycle sequence matches
  RED,RED,RED,GREEN,GREEN,GREEN,YELLOW,RED.

All six parse under Pyverilog (no Verible fallback needed).

## Fix E — sensitivity-list false positive

`sensitivity_list_error` fired on **all three** correct SEQ testbenches. Same family as
the `$fdisplay` false positive in `008`: the check encoded one testbench style and
flagged every other correct one.

Two ordinary constructions were being flagged:

1. A clock generator, `always #5 clk = ~clk;`, has no sensitivity list by design. It was
   counted as "an always-block with no edge trigger" — which flagged every testbench that
   generates its own clock, i.e. all of them.
2. A self-checking testbench synchronises with `@(posedge clk)` event controls from inside
   an `initial` block rather than with an edge-triggered `always`. That *is* edge
   synchronisation; it is simply not in a sensitivity list.

Now: always-blocks with no sensitivity list are ignored, and an edge event control
anywhere in the source satisfies the check. A testbench that drives a sequential DUT with
bare delays and never synchronises to an edge is still flagged (unit test).

## Fault-injection preview

With the fixtures in place and fix E applied, the checks fire — and stay silent on
correct testbenches:

| Injected fault | Detected as |
|---|---|
| `alu_8bit`: `.op` → `.opcode` | `port_binding_mismatch` (×2: unknown port + unbound port) |
| `alu_8bit`: `.overflow` binding removed | `port_binding_mismatch` |
| `alu_8bit`: `op` never assigned | `undriven_input` |
| `alu_8bit`: `carry` never compared | `unobserved_output` |
| `fifo_8x8`: `.rd_en` → `.read_en` | `port_binding_mismatch` (×2) |
| `fifo_8x8`: `data_in` never assigned | `undriven_input` |
| `fifo_8x8`: `data_out` never checked | `missing_fdisplay` (SEQ-specific class) |
| *correct testbench, all six circuits* | **no findings** |

Regression: the 32 saved testbenches from the July sweep still produce 0 findings and
29/32 Pyverilog parses.

## Known gaps carried into Day 3

- **`WIDTH_MISMATCH` is still never emitted.** Declared in the taxonomy, implemented
  nowhere. Either implement it against these mixed-width circuits or remove it from the
  taxonomy — the report must not claim a check that does not exist.
- **A clock that is initialised but never toggled is not caught.** Removing
  `always #5 clk = ~clk;` leaves the analyser clean, because `initial clk = 0;` satisfies
  `_signal_is_driven`. The deterministic standardiser repairs this case
  (`_has_clock_gen`), but the analyser does not report it. A `CLOCK_NEVER_TOGGLED` check
  is cheap and would be a genuine addition — quantify it in the Day-3 injection study
  before deciding.

## Fix F — Eval1 verdict decided by a scenario name

The smoke run earned its keep. `fsm_sequence_detector` printed **8 PASS lines and no
FAIL line**, was scored a failure, and then burned **all three repair iterations** trying
to fix a testbench that was already correct — ending `exhausted_iters`.

Cause: the Eval1 verdict searched the whole simulation output for the bare substring
`"mismatch"`, and one scenario was named `immediate_mismatch`. The scenario's *name* was
scoring its own run.

Unfixed, this would have produced a wrong row for any circuit whose generated scenario
names happen to contain the word — plausible for comparators, ALUs and FSMs — and would
have burned three repair calls per occurrence. The verdict now inspects line by line,
skips `PASS:` verdict lines (their names are free text), and treats a zero-count report
as the success it is (a VerilogEval reference testbench prints `Mismatches: 0 in N
samples` when nothing went wrong).

## Smoke runs

One `hybrid` run per hard circuit, before committing to the paid sweep.

| Circuit | Eval0 | Eval1 | Eval2 | repairs | scenarios |
|---|---|---|---|---|---|
| `alu_8bit` | ✅ | ✅ | 1.00 (5/5 valid) | 1 (sim) | 10/10 |
| `barrel_shifter_8bit` | ✅ | ✅ | 1.00 (5/5 valid) | 1 (sim) | 8/8 |
| `bcd_to_7seg` | ✅ | ✅ | 1.00 (5/5 valid) | 0 | 16/16 |
| `fifo_8x8` | ✅ | ✅ | 1.00 (**3/3 valid of 5**) | 0 | 8/8 |
| `traffic_light_fsm` | ✅ | ✅ | 0.80 (4/5 valid) | 3 (sim) | 7/7 |
| `fsm_sequence_detector` | ✅ | ✗ → **✅ after F** | 1.00 (5/5 valid) | 3 wasted → 1 (sim) | 8/8 → 9/9 |

Results in `results/day2_smoke/` and `results/day2_smoke_seq/`.

Two observations worth carrying forward:

- **The difficulty level is right.** `alu_8bit` and `barrel_shifter_8bit` failed first-shot
  on exactly the hard cases — arithmetic right shift of a negative value, signed
  comparison — and recovered in one repair. `traffic_light_fsm` needed all three. These
  circuits discriminate between modes, which the original CMB fixtures did not.
- **Fix D is visibly load-bearing.** `fifo_8x8` caught 3 of 3 *valid* mutants, but only 3
  of the 5 generated mutants compiled. Under the old denominator it would have scored
  0.60 instead of 1.00 — a 40-point error on a testbench that missed nothing.

## Validation

Full suite: **126 passed, 3 skipped** (was 88/3). 38 new tests — fixture integrity,
compilation, Pyverilog parse, no-false-positive, injected-fault detection, and three
sensitivity-list style cases.
