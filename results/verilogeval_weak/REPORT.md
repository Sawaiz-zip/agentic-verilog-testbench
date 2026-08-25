# Evaluation Sweep

**Source:** `results/verilogeval_weak`  
**Circuits:** 20  ·  **Modes:** 5  ·  **Records:** 100

**Temperature:** 0.7  
**Models:** `openai/gpt-4o-mini`


## Completeness

- Runs recorded: **100 / 100** expected
- Harness errors: **0**

## Results by mode

| mode | n | Eval0 | Eval1 | Eval2 | mean repairs | tokens in | tokens out | mean wall |
|---|---|---|---|---|---|---|---|---|
| `baseline` | 20 | 95% | 10% | 9% | 0.00 | 6,409 | 3,801 | 43s |
| `retry_only` | 20 | 70% | 10% | 10% | 1.00 | 8,184 | 4,387 | 55s |
| `compiler_only` | 20 | 90% | 5% | 5% | 0.30 | 7,253 | 3,865 | 44s |
| `pyverilog_only` | 20 | 90% | 5% | 5% | 0.00 | 6,265 | 3,651 | 42s |
| `hybrid` | 20 | 95% | 10% | 10% | 1.35 | 11,085 | 5,405 | 68s |

> `retry_only` is the control arm: one extra generation with **no** diagnostics. A mode must beat it, not merely `baseline`, for its feedback to be doing the work.


## Per-circuit outcomes

✅ = Eval1 pass, ❌ = fail; the digit is the number of repair iterations used.

| circuit | type | `baseline` | `retry_only` | `compiler_only` | `pyverilog_only` | `hybrid` |
|---|---|---|---|---|---|---|
| `Prob064_vector3` | CMB | ❌ | ❌1 | ❌ | ❌ | ❌ |
| `Prob065_7420` | CMB | ❌ | ✅1 | ✅ | ❌ | ✅ |
| `Prob081_7458` | CMB | ❌ | ✅1 | ❌ | ✅ | ✅ |
| `Prob084_ece241_2013_q12` | SEQ | ❌ | ❌1 | ❌ | ❌ | ❌3 |
| `Prob085_shift4` | SEQ | ❌ | ❌1 | ❌ | ❌ | ❌3 |
| `Prob087_gates` | CMB | ✅ | ❌1 | ❌ | ❌ | ❌1 |
| `Prob115_shift18` | SEQ | ❌ | ❌1 | ❌ | ❌ | ❌1 |
| `Prob118_history_shift` | SEQ | ❌ | ❌1 | ❌ | ❌ | ❌1 |
| `Prob127_lemmings1` | SEQ | ✅ | ❌1 | ❌ | ❌ | ❌3 |
| `Prob139_2013_q2bfsm` | SEQ | ❌ | ❌1 | ❌3 | ❌ | ❌3 |
| `Prob140_fsm_hdlc` | SEQ | ❌ | ❌1 | ❌ | ❌ | ❌ |
| `Prob141_count_clock` | SEQ | ❌ | ❌1 | ❌ | ❌ | ❌1 |
| `Prob142_lemmings2` | SEQ | ❌ | ❌1 | ❌ | ❌ | ❌1 |
| `Prob149_ece241_2013_q4` | SEQ | ❌ | ❌1 | ❌ | ❌ | ❌3 |
| `Prob150_review2015_fsmonehot` | SEQ | ❌ | ❌1 | ❌3 | ❌ | ❌1 |
| `Prob151_review2015_fsm` | SEQ | ❌ | ❌1 | ❌ | ❌ | ❌ |
| `Prob152_lemmings3` | SEQ | ❌ | ❌1 | ❌ | ❌ | ❌3 |
| `Prob153_gshare` | SEQ | ❌ | ❌1 | ❌ | ❌ | ❌ |
| `Prob155_lemmings4` | SEQ | ❌ | ❌1 | ❌ | ❌ | ❌ |
| `Prob156_review2015_fancytimer` | SEQ | ❌ | ❌1 | ❌ | ❌ | ❌3 |

## Repair feedback sources

What actually triggered each repair — the mechanism behind any gain.

| mode | repairs | static | compile | simulation | none (control) |
|---|---|---|---|---|---|
| `baseline` | 0 | 0 | 0 | 0 | 0 |
| `retry_only` | 20 | 0 | 0 | 0 | 20 |
| `compiler_only` | 6 | 0 | 6 | 0 | 0 |
| `pyverilog_only` | 0 | 0 | 0 | 0 | 0 |
| `hybrid` | 27 | 0 | 2 | 25 | 0 |

## Static findings on real generated testbenches

- Analysis passes: **153**  ·  Pyverilog parse failures: **0**

| finding | count |
|---|---|
| `port_binding_mismatch` | 8 |

## Eval2 mutant quality

- Mutants generated: **40**  ·  compiled (valid): **40**  ·  caught: **39**
- Invalid mutants excluded from scoring: **0** (0% of generated)

> A mutant that does not compile is a bad mutation, not a testbench failure, so it is excluded from both numerator and denominator.

## Final status distribution

| mode | exhausted_iters | failed_compile | failed_eval1 | oscillated | success |
|---|---|---|---|---|---|
| `baseline` | 0 | 1 | 17 | 0 | 2 |
| `retry_only` | 0 | 6 | 12 | 0 | 2 |
| `compiler_only` | 2 | 0 | 17 | 0 | 1 |
| `pyverilog_only` | 0 | 2 | 17 | 0 | 1 |
| `hybrid` | 7 | 0 | 0 | 11 | 2 |

## Worth a second look

- `RefModule × baseline` — did not compile
- `RefModule × compiler_only` — did not compile
- `RefModule × compiler_only` — used the full repair budget without passing
- `RefModule × hybrid` — did not compile
- `RefModule × hybrid` — oscillated (same error recurring)
- `RefModule × hybrid` — used the full repair budget without passing
- `RefModule × pyverilog_only` — did not compile
- `RefModule × retry_only` — did not compile
