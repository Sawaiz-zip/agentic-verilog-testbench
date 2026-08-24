# 012 — Pre-flight Hardening for the Evaluation Sweep

**Date:** 2026-08-25 · **Branch:** `012-preflight-hardening`

The Day-4 sweep is 120 runs over 4–6 hours costing ~$15, and the budget allows it **once**.
This is the verification pass before committing to it. Ten checks; three defects found.

## Checks

| # | Check | Result |
|---|---|---|
| 1 | All 12 circuits resolve to the intended fixture (not shadowed by a VerilogEval substring match) | ✅ 0 failures; `module_name`, `task_id`, DUT and description all correct |
| 2 | All 5 ablation modes compile a graph | ✅ |
| 3 | Modes are behaviourally **distinct** | ✅ unique routing row per mode |
| 4 | Run count | ✅ 60/repeat, 120 total |
| 5 | Provider config | ✅ `claude-sonnet-4.5` + `gpt-4o-mini`, **temp 0.7**, key present |
| 6 | Aggregator handles 5 modes; `task_id` de-dup | ✅ n correct per mode; 3 duplicate records → n=1 |
| 7 | Injectors still valid | ✅ 73 faults re-injected, **0 invalid Verilog**, baselines clean, saved study reproduces exactly |
| 8 | Full offline suite | ✅ 195 passed, 3 skipped |
| 9 | **Live** end-to-end run against the real API | ✅ all result fields present; `clock_errors` serialised, no stale `sensitivity_errors`; temp 0.7 confirmed in the call log |
| 10 | Repeat aggregation across two sweeps | ✅ mean±std over all 5 modes |

### Mode routing matrix (check 3)

| mode | static error | clean static | compile fail | sim fail |
|---|---|---|---|---|
| `baseline` | evaluate | evaluate | END | END |
| `retry_only` | **regenerate** | **regenerate** | END | END |
| `compiler_only` | evaluate | evaluate | **repair** | END |
| `pyverilog_only` | **repair** | evaluate | END | END |
| `hybrid` | **repair** | evaluate | **repair** | **repair** |

Every row differs, so no two arms can collapse into each other.

### Live differential (check 9, extended)

The same circuit under two arms, real API:

| mode | repairs | feedback | scenarios | outcome |
|---|---|---|---|---|
| `pyverilog_only` | 0 | none — static clean, so it correctly declines to repair | 7/8 | `failed_eval1` |
| `hybrid` | 1 | simulation | 37/37 | `success` |

The arms differ in practice, not merely in the routing table.

## Defects found

**1. An exhausted balance had no handling.** The sweep only aborted on a *daily rate limit*.
On a 402 every remaining (module, mode) pair would have failed individually, each with its
own retries and exponential backoff — hours of wall time producing records that say nothing,
and burying the runs that had already succeeded. `_is_out_of_credits()` now recognises HTTP
402 and the common message variants, aborts immediately, and still aggregates what
completed, so the run resumes into the same `--results-dir`.

**2. The abort did not actually stop the sweep.** Writing the test for (1) exposed it:
`run_sweep` set the abort flag but the inner mode loop had no `break`, so one further run was
attempted after the failure. The daily-rate-limit path had a `break`; the new one did not.
Now covered by a test asserting the exact invocation count — and by its opposite, that a
*transient* failure must **not** abort, since one bad run ending the sweep would be worse
than no abort at all.

**3. `aggregate_repeats.py` was silently dropping `retry_only`.** It carried a hardcoded
mode list written before the control arm existed. Day 5 would have produced mean±std tables
missing the one arm that makes the comparison sound — and nothing would have complained. It
now derives the list from `harness.ALL_MODES`, so a future mode cannot go missing the same way.

## Day-4 launch

```bash
python scripts/run_eval.py --yes --results-dir results/final_hard_r1 --modules \
  alu_1bit comparator_2bit priority_encoder alu_8bit barrel_shifter_8bit bcd_to_7seg \
  dff counter_4bit shift_register fsm_sequence_detector fifo_8x8 traffic_light_fsm
```

Repeat 2 into `results/final_hard_r2`, then
`python scripts/aggregate_repeats.py results/final_hard_r1 results/final_hard_r2`.

Freeze the prompts and tag `prompts-frozen` before the first launch.

## Note on cost

Pre-flight spent ~$0.40 on two live runs. That bought confirmation that the real API path
works end to end with the current code — which the mocked suite cannot show, since the
`sensitivity_errors` → `clock_errors` rename touches serialisation that only runs live.
