# 009 — Hard Circuit Fixtures (Day 2)

**Date:** 2026-08-24 · **Branch:** `009-hard-circuit-fixtures`

Day 2 of the 5-day plan in `TODO.md`. Builds the six circuits the evaluation set was
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

## Smoke runs

One `hybrid` run per hard circuit, before committing to the paid sweep.
Results in `results/day2_smoke/`.

## Validation

Full suite: **126 passed, 3 skipped** (was 88/3). 38 new tests — fixture integrity,
compilation, Pyverilog parse, no-false-positive, injected-fault detection, and three
sensitivity-list style cases.
