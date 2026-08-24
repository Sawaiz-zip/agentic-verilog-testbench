# 010 — WIDTH_MISMATCH & CLOCK_NEVER_TOGGLED

**Date:** 2026-08-24 · **Branch:** `010-width-and-clock-checks`

Closes the two gaps `009` carried forward, before the Day-3 injection study measures the
localiser. Both target defects **the compiler cannot see**, which is the case static
analysis has to make.

## WIDTH_MISMATCH — declared since the start, emitted nowhere

`ErrorType.WIDTH_MISMATCH` had been in the taxonomy since Phase 2 and no code path ever
produced it. The report would have claimed a check that did not exist.

It also could not have been tested before now: **every original fixture is 1-bit or
uniformly 4-bit**, so there is no width for a testbench to get wrong. The mixed-width
circuits from `009` (`alu_8bit` 8/3/1, `barrel_shifter_8bit` 8/3/1, `bcd_to_7seg` 4→7,
`fifo_8x8` 8/4/1) are what made it testable.

Implementation compares each DUT port's declared width against the testbench signal bound
to it:

- Reads **both declaration styles** — ANSI (`module m(input [7:0] a);`) carries the width
  on the port, Verilog-1995 (`module m(a); input [7:0] a;`) on a separate declaration.
- A port with no width declaration is 1 bit, so a scalar port bound to a plain `reg`
  compares equal rather than reading as unknown.
- **Skips what it cannot resolve** — parameterised widths, concatenations, slices and
  expressions produce no finding rather than a guess.
- The suggested fix names both widths and the correct declaration, so it is actionable
  without opening the DUT.

Why it matters: a width mismatch is **silent at simulation time**. Verilog truncates or
zero-extends without a warning, so the testbench compiles, runs, and reports wrong
results. Neither Eval0 nor the simulator can find it.

## CLOCK_NEVER_TOGGLED — a hole between two existing checks

Found in `009`: deleting `always #5 clk = ~clk;` from a correct testbench left the
analyser completely clean. `initial clk = 0;` satisfies `_signal_is_driven`, so the
undriven-input check cannot see it, and no other check looks at clock behaviour.

The consequence is nastier than a missing signal: the simulation compiles and runs, it
simply never advances. Every scenario reads back the reset value, so the failure presents
as a logic error rather than as a missing clock — expensive to diagnose, and exactly the
kind of thing the repair loop would burn its whole budget on.

Design choices:

- The clock is identified from **edge expressions in the DUT source** intersected with its
  input ports, not from a name convention. A clock called `ck` or `pclk` is found; a data
  signal called `clock_enable` is not.
- Toggle detection is **deliberately generous**. After three false positives in this
  module (`$fdisplay` in 008, sensitivity list in 009, Eval1 verdict in 009), the failure
  mode to avoid is flagging correct code. Any inversion, any assignment inside an
  `always`/`forever`/`repeat`, or more than one assignment anywhere counts as toggling.
- A clock with **no** assignment is left to the undriven-input check, so the two never
  report the same defect.

Verified silent on four working generator styles: `always #5 clk = ~clk;`,
`initial forever #5 clk = ~clk;`, `always begin #5 clk=1; #5 clk=0; end` (no inversion at
all), and non-blocking `always #5 clk <= ~clk;`.

## Guard against this recurring

`test_every_declared_error_type_is_actually_emitted_somewhere` asserts that every member
of `ErrorType` appears in an `ErrorType.X` construction in the runner. `parse_failed` is
exempt — it is carried by `PyverilogReport(parse_ok=False)` rather than as an
`ErrorReportItem`. An unbacked taxonomy entry can no longer reach the report.

## Validation

| Injected fault | Detected |
|---|---|
| `alu_8bit`: `op` declared `[1:0]`, port is `[2:0]` | `width_mismatch` |
| `alu_8bit`: `result` declared `[3:0]`, port is `[7:0]` | `width_mismatch` |
| `alu_8bit`: `a` declared scalar, port is `[7:0]` | `width_mismatch` |
| `alu_8bit`: `zero` declared `[3:0]`, port is scalar | `width_mismatch` |
| `barrel_shifter_8bit`: `shamt` `[1:0]` vs `[2:0]` | `width_mismatch` |
| `bcd_to_7seg`: `seg` `[3:0]` vs `[6:0]` | `width_mismatch` |
| `fifo_8x8`: `data_in` `[3:0]` vs `[7:0]` | `width_mismatch` |
| `fifo_8x8` / `traffic_light_fsm`: clock generator deleted | `clock_never_toggled` |
| *four working clock-generator styles* | **no finding** |
| *correct testbench, all six hard fixtures* | **no finding** |

**Regression: zero findings across all 38 real testbenches** — the 32 saved from the July
sweep and the 6 passing Day-2 smoke runs.

Full suite: **153 passed, 3 skipped** (was 132/3). 21 new tests.

## Check inventory going into Day 3

| Check | Status |
|---|---|
| `port_binding_mismatch` | ✅ fires, verified by injection |
| `undriven_input` | ✅ fires, verified by injection |
| `unobserved_output` | ✅ fires, verified by injection |
| `missing_fdisplay` (SEQ) | ✅ fires, de-duplicated against `unobserved_output` |
| `width_mismatch` | ✅ **now implemented**, verified on 4 circuits |
| `clock_never_toggled` (SEQ) | ✅ **new**, verified on 2 circuits |
| `sensitivity_list_error` | ⚠️ fires only when a testbench never synchronises to an edge — rare in practice. Day 3 will quantify whether it earns its place. |

Six of seven are now injection-verified. Day 3 turns this from a spot check into
precision/recall figures.
