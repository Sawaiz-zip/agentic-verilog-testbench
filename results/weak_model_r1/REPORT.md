# Evaluation Sweep

**Source:** `results/weak_model_r1`  
**Circuits:** 12  ·  **Modes:** 5  ·  **Records:** 60

**Temperature:** 0.7  
**Models:** `openai/gpt-4o-mini`


## Completeness

- Runs recorded: **60 / 60** expected
- Harness errors: **0**

## Results by mode

| mode | n | Eval0 | Eval1 | Eval2 | mean repairs | tokens in | tokens out | mean wall |
|---|---|---|---|---|---|---|---|---|
| `baseline` | 12 | 92% | 17% | 17% | 0.00 | 5,580 | 3,369 | 35s |
| `retry_only` | 12 | 75% | 25% | 25% | 1.00 | 7,144 | 4,244 | 47s |
| `compiler_only` | 12 | 100% | 50% | 42% | 0.00 | 5,380 | 3,286 | 38s |
| `pyverilog_only` | 12 | 83% | 33% | 27% | 0.00 | 5,466 | 3,071 | 36s |
| `hybrid` | 12 | 92% | 50% | 50% | 0.58 | 7,794 | 4,081 | 49s |

> `retry_only` is the control arm: one extra generation with **no** diagnostics. A mode must beat it, not merely `baseline`, for its feedback to be doing the work.


## Per-circuit outcomes

✅ = Eval1 pass, ❌ = fail; the digit is the number of repair iterations used.

| circuit | type | `baseline` | `retry_only` | `compiler_only` | `pyverilog_only` | `hybrid` |
|---|---|---|---|---|---|---|
| `alu_1bit` | CMB | ✅ | ✅1 | ✅ | ✅ | ✅ |
| `alu_8bit` | CMB | ❌ | ❌1 | ✅ | ❌ | ❌3 |
| `barrel_shifter_8bit` | CMB | ❌ | ❌1 | ❌ | ❌ | ❌ |
| `bcd_to_7seg` | CMB | ✅ | ✅1 | ✅ | ✅ | ✅ |
| `comparator_2bit` | CMB | ❌ | ✅1 | ✅ | ✅ | ✅ |
| `counter_4bit` | SEQ | ❌ | ❌1 | ❌ | ❌ | ❌1 |
| `dff` | SEQ | ❌ | ❌1 | ✅ | ❌ | ✅ |
| `fifo_8x8` | SEQ | ❌ | ❌1 | ❌ | ❌ | ❌3 |
| `fsm_sequence_detector` | SEQ | ❌ | ❌1 | ❌ | ❌ | ❌ |
| `priority_encoder` | CMB | ❌ | ❌1 | ✅ | ✅ | ✅ |
| `shift_register` | SEQ | ❌ | ❌1 | ❌ | ❌ | ✅ |
| `traffic_light_fsm` | SEQ | ❌ | ❌1 | ❌ | ❌ | ❌ |

## Repair feedback sources

What actually triggered each repair — the mechanism behind any gain.

| mode | repairs | static | compile | simulation | none (control) |
|---|---|---|---|---|---|
| `baseline` | 0 | 0 | 0 | 0 | 0 |
| `retry_only` | 12 | 0 | 0 | 0 | 12 |
| `compiler_only` | 0 | 0 | 0 | 0 | 0 |
| `pyverilog_only` | 0 | 0 | 0 | 0 | 0 |
| `hybrid` | 7 | 0 | 0 | 7 | 0 |

## Static findings on real generated testbenches

- Analysis passes: **79**  ·  Pyverilog parse failures: **3**

| finding | count |
|---|---|
| `port_binding_mismatch` | 1 |

## Eval2 mutant quality

- Mutants generated: **105**  ·  compiled (valid): **105**  ·  caught: **96**
- Invalid mutants excluded from scoring: **0** (0% of generated)

> A mutant that does not compile is a bad mutation, not a testbench failure, so it is excluded from both numerator and denominator.

## Final status distribution

| mode | exhausted_iters | failed_compile | failed_eval1 | failed_eval2 | oscillated | success |
|---|---|---|---|---|---|---|
| `baseline` | 0 | 1 | 9 | 0 | 0 | 2 |
| `retry_only` | 0 | 3 | 6 | 0 | 0 | 3 |
| `compiler_only` | 0 | 0 | 6 | 1 | 0 | 5 |
| `pyverilog_only` | 0 | 2 | 6 | 0 | 0 | 4 |
| `hybrid` | 2 | 0 | 0 | 0 | 4 | 6 |

## Worth a second look

- `alu_1bit × compiler_only` — passes Eval1 but catches no mutants (tests nothing)
- `alu_8bit × hybrid` — used the full repair budget without passing
- `barrel_shifter_8bit × hybrid` — oscillated (same error recurring)
- `counter_4bit × hybrid` — oscillated (same error recurring)
- `counter_4bit × retry_only` — did not compile
- `fifo_8x8 × hybrid` — used the full repair budget without passing
- `fsm_sequence_detector × hybrid` — oscillated (same error recurring)
- `fsm_sequence_detector × pyverilog_only` — did not compile
- `fsm_sequence_detector × retry_only` — did not compile
- `shift_register × retry_only` — did not compile
- `traffic_light_fsm × baseline` — did not compile
- `traffic_light_fsm × hybrid` — did not compile
- `traffic_light_fsm × hybrid` — oscillated (same error recurring)
- `traffic_light_fsm × pyverilog_only` — did not compile
