# Evaluation Sweep

**Source:** `results/final_hard_r1`  
**Circuits:** 12  ·  **Modes:** 5  ·  **Records:** 60

**Temperature:** 0.7  
**Models:** `anthropic/claude-sonnet-4.5`, `openai/gpt-4o-mini`


## Completeness

- Runs recorded: **60 / 60** expected
- Harness errors: **0**

## Results by mode

| mode | n | Eval0 | Eval1 | Eval2 | mean repairs | tokens in | tokens out | mean wall |
|---|---|---|---|---|---|---|---|---|
| `baseline` | 12 | 92% | 67% | 67% | 0.00 | 5,884 | 4,486 | 47s |
| `retry_only` | 12 | 100% | 67% | 67% | 1.00 | 8,482 | 6,032 | 63s |
| `compiler_only` | 12 | 100% | 67% | 67% | 0.00 | 6,563 | 4,615 | 49s |
| `pyverilog_only` | 12 | 100% | 33% | 33% | 0.00 | 6,184 | 4,323 | 43s |
| `hybrid` | 12 | 100% | 83% | 82% | 0.83 | 9,576 | 5,620 | 61s |

> `retry_only` is the control arm: one extra generation with **no** diagnostics. A mode must beat it, not merely `baseline`, for its feedback to be doing the work.


## Per-circuit outcomes

✅ = Eval1 pass, ❌ = fail; the digit is the number of repair iterations used.

| circuit | type | `baseline` | `retry_only` | `compiler_only` | `pyverilog_only` | `hybrid` |
|---|---|---|---|---|---|---|
| `alu_1bit` | CMB | ✅ | ✅1 | ✅ | ✅ | ✅ |
| `alu_8bit` | CMB | ❌ | ✅1 | ✅ | ❌ | ✅1 |
| `barrel_shifter_8bit` | CMB | ✅ | ❌1 | ❌ | ❌ | ✅ |
| `bcd_to_7seg` | CMB | ✅ | ✅1 | ✅ | ✅ | ✅ |
| `comparator_2bit` | CMB | ✅ | ✅1 | ✅ | ✅ | ✅ |
| `counter_4bit` | SEQ | ❌ | ❌1 | ❌ | ❌ | ❌3 |
| `dff` | SEQ | ✅ | ✅1 | ✅ | ❌ | ✅ |
| `fifo_8x8` | SEQ | ✅ | ✅1 | ✅ | ✅ | ❌3 |
| `fsm_sequence_detector` | SEQ | ❌ | ✅1 | ❌ | ❌ | ✅ |
| `priority_encoder` | CMB | ✅ | ✅1 | ✅ | ❌ | ✅1 |
| `shift_register` | SEQ | ✅ | ❌1 | ❌ | ❌ | ✅ |
| `traffic_light_fsm` | SEQ | ❌ | ❌1 | ✅ | ❌ | ✅2 |

## Repair feedback sources

What actually triggered each repair — the mechanism behind any gain.

| mode | repairs | static | compile | simulation | none (control) |
|---|---|---|---|---|---|
| `baseline` | 0 | 0 | 0 | 0 | 0 |
| `retry_only` | 12 | 0 | 0 | 0 | 12 |
| `compiler_only` | 0 | 0 | 0 | 0 | 0 |
| `pyverilog_only` | 0 | 0 | 0 | 0 | 0 |
| `hybrid` | 10 | 0 | 0 | 10 | 0 |

## Static findings on real generated testbenches

- Analysis passes: **82**  ·  Pyverilog parse failures: **1**
- **No structural findings.** The generated testbenches were structurally clean; the defects that remained were behavioural, which static analysis cannot see.

## Eval2 mutant quality

- Mutants generated: **190**  ·  compiled (valid): **190**  ·  caught: **189**
- Invalid mutants excluded from scoring: **0** (0% of generated)

> A mutant that does not compile is a bad mutation, not a testbench failure, so it is excluded from both numerator and denominator.

## Final status distribution

| mode | exhausted_iters | failed_compile | failed_eval1 | success |
|---|---|---|---|---|
| `baseline` | 0 | 1 | 3 | 8 |
| `retry_only` | 0 | 0 | 4 | 8 |
| `compiler_only` | 0 | 0 | 4 | 8 |
| `pyverilog_only` | 0 | 0 | 8 | 4 |
| `hybrid` | 2 | 0 | 0 | 10 |

## Worth a second look

- `alu_8bit × baseline` — did not compile
- `counter_4bit × hybrid` — used the full repair budget without passing
- `fifo_8x8 × hybrid` — used the full repair budget without passing
