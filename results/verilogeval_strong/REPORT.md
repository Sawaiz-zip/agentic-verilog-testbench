# Evaluation Sweep

**Source:** `results/verilogeval_strong`  
**Circuits:** 20  ·  **Modes:** 3  ·  **Records:** 60

**Temperature:** 0.7  
**Models:** `anthropic/claude-sonnet-4.5`, `openai/gpt-4o-mini`


## Completeness

- Runs recorded: **60 / 60** expected
- Harness errors: **0**

## Results by mode

| mode | n | Eval0 | Eval1 | Eval2 | mean repairs | tokens in | tokens out | mean wall |
|---|---|---|---|---|---|---|---|---|
| `baseline` | 20 | 95% | 25% | 20% | 0.00 | 7,506 | 5,639 | 47s |
| `retry_only` | 20 | 100% | 30% | 30% | 1.00 | 9,807 | 7,084 | 59s |
| `hybrid` | 20 | 100% | 50% | 44% | 2.00 | 15,657 | 8,877 | 77s |

> `retry_only` is the control arm: one extra generation with **no** diagnostics. A mode must beat it, not merely `baseline`, for its feedback to be doing the work.


## Per-circuit outcomes

✅ = Eval1 pass, ❌ = fail; the digit is the number of repair iterations used.

| circuit | type | `baseline` | `retry_only` | `hybrid` |
|---|---|---|---|---|
| `Prob064_vector3` | CMB | ❌ | ❌1 | ❌3 |
| `Prob065_7420` | CMB | ✅ | ✅1 | ✅ |
| `Prob081_7458` | CMB | ✅ | ✅1 | ✅ |
| `Prob084_ece241_2013_q12` | SEQ | ❌ | ❌1 | ✅1 |
| `Prob085_shift4` | SEQ | ✅ | ✅1 | ✅ |
| `Prob087_gates` | CMB | ❌ | ✅1 | ✅ |
| `Prob115_shift18` | SEQ | ❌ | ❌1 | ✅1 |
| `Prob118_history_shift` | SEQ | ❌ | ❌1 | ✅3 |
| `Prob127_lemmings1` | SEQ | ✅ | ✅1 | ✅ |
| `Prob139_2013_q2bfsm` | SEQ | ❌ | ❌1 | ❌3 |
| `Prob140_fsm_hdlc` | SEQ | ❌ | ❌1 | ✅2 |
| `Prob141_count_clock` | SEQ | ❌ | ❌1 | ❌3 |
| `Prob142_lemmings2` | SEQ | ✅ | ❌1 | ❌3 |
| `Prob149_ece241_2013_q4` | SEQ | ❌ | ❌1 | ❌3 |
| `Prob150_review2015_fsmonehot` | SEQ | ❌ | ❌1 | ❌3 |
| `Prob151_review2015_fsm` | SEQ | ❌ | ❌1 | ❌3 |
| `Prob152_lemmings3` | SEQ | ❌ | ❌1 | ✅3 |
| `Prob153_gshare` | SEQ | ❌ | ❌1 | ❌3 |
| `Prob155_lemmings4` | SEQ | ❌ | ✅1 | ❌3 |
| `Prob156_review2015_fancytimer` | SEQ | ❌ | ❌1 | ❌3 |

## Repair feedback sources

What actually triggered each repair — the mechanism behind any gain.

| mode | repairs | static | compile | simulation | none (control) |
|---|---|---|---|---|---|
| `baseline` | 0 | 0 | 0 | 0 | 0 |
| `retry_only` | 20 | 0 | 0 | 0 | 20 |
| `hybrid` | 40 | 1 | 2 | 37 | 0 |

## Static findings on real generated testbenches

- Analysis passes: **120**  ·  Pyverilog parse failures: **0**

| finding | count |
|---|---|
| `port_binding_mismatch` | 4 |

## Eval2 mutant quality

- Mutants generated: **105**  ·  compiled (valid): **102**  ·  caught: **91**
- Invalid mutants excluded from scoring: **3** (3% of generated)

> A mutant that does not compile is a bad mutation, not a testbench failure, so it is excluded from both numerator and denominator.

## Final status distribution

| mode | exhausted_iters | failed_compile | failed_eval1 | failed_eval2 | success |
|---|---|---|---|---|---|
| `baseline` | 0 | 1 | 14 | 1 | 4 |
| `retry_only` | 0 | 0 | 14 | 0 | 6 |
| `hybrid` | 10 | 0 | 0 | 1 | 9 |

## Worth a second look

- `RefModule × baseline` — did not compile
- `RefModule × baseline` — passes Eval1 but catches no mutants (tests nothing)
- `RefModule × hybrid` — passes Eval1 but catches no mutants (tests nothing)
- `RefModule × hybrid` — used the full repair budget without passing
