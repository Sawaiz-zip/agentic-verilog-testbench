# Agentic Verilog Testbench Generation

**A multi-agent pipeline that writes Verilog testbenches from natural language, finds structural faults *before* simulation, and repairs them from structured feedback.**

Built on LangGraph (orchestration), Pyverilog (static analysis) and Icarus Verilog (evaluation).

[![tests](https://img.shields.io/badge/tests-195%20passed-brightgreen)]()
[![fault detection](https://img.shields.io/badge/fault%20detection-93%25-blue)]()
[![false positives](https://img.shields.io/badge/false%20positives-0%2F14-blue)]()
[![python](https://img.shields.io/badge/python-3.11%2B-blue)]()

---

## The problem

Hardware verification consumes roughly 60% of chip design effort, and writing testbenches is a large part of it. LLMs can draft one in seconds — but the failure mode is nasty: **the output is usually syntactically valid and functionally wrong**. It compiles, it runs, it reports success, and it never actually tested the thing.

The worst case is a testbench that stops checking one of the outputs. It doesn't fail. It **passes** — because it is no longer looking.

The usual remedy is to run a full simulation and read the output. That is slow, and it cannot catch the case above at all: the simulator has nothing to observe.

## The approach

Analyse the generated testbench statically, before any simulation, and hand the model a precise defect report instead of a wall of simulator output.

```
natural language  ──▶  classify ──▶ generate DUT ──▶ extract spec ──▶ scenarios
                                                                        │
                                            ┌───────────────────────────┴──────────┐
                                            ▼                                      ▼
                                    generate driver                        generate checker
                                            └───────────────┬──────────────────────┘
                                                            ▼
                                              standardise (sequential only)
                                                            ▼
                                            ┌──▶  Pyverilog static analysis
                                            │               ▼
                                            │       LLM error reasoner
                                            │               ▼
                                            └───────────  repair  ◀──┐
                                                            ▼        │
                                                   Icarus evaluation │
                                                   Eval0 / 1 / 2 ────┘
```

Every step is an explicit LangGraph node with explicit conditional edges — no hidden control flow. Repair is bounded, with oscillation detection and best-so-far retention so more repair can never produce a worse artifact.

## Results

**220 pipeline runs** across three sweeps, plus an offline fault-injection study.
Full detail and reproduction commands in [`docs/results.md`](docs/results.md).

### The localiser works

Fault injection: 14 known-good testbenches, 215 injected faults, three layers asked the
same question.

| | static | compiler | simulator |
|---|---|---|---|
| Detection | **93%** | 29% | 56% |
| Localisation (class **and** signal) | **93%** | — | — |
| False positives on clean input | **0 / 14** | — | — |

**33 of 215 faults (15%) are invisible to the compiler and the simulator together. Static
analysis catches 30 of them.** The clearest case: a testbench that stops checking an
output does not fail — it *passes*, because it is no longer looking.

### But the faults it catches are rare in practice

| Sweep | Model | Analyses | Runs with a finding |
|---|---|---|---|
| 12 project circuits | `claude-sonnet-4.5` | 82 | **0 / 60** |
| 12 project circuits | `gpt-4o-mini` | 79 | **1 / 60** |
| 20 VerilogEval circuits | `gpt-4o-mini` | 153 | **1 / 100** |

**2 findings in 314 analyses.** Both a weak and a strong model produce structurally
well-formed testbenches; **87% of real failures are semantic** (133 of 153) and require
simulation by definition.

### Ablation, pooled (n=44 per mode)

| mode | Eval1 | 95% CI | tokens vs baseline |
|---|---|---|---|
| `pyverilog_only` | 20.5% | [11.2, 34.5] | −2% |
| `baseline` | 27.3% | [16.3, 41.8] | — |
| `retry_only` | 29.5% | [18.2, 44.2] | +29% |
| `compiler_only` | 34.1% | [21.9, 48.9] | +6% |
| **`hybrid`** | **40.9%** | [27.7, 55.6] | +50% |

**No pairwise difference reaches p < 0.05** (hybrid vs the `retry_only` control: p = 0.372).
Arms that took an identical code path scored 33 points apart — a variance floor reproduced
independently in two sweeps. At temperature 0.7 with this sample size, differences below
~33 points are not interpretable.

That measurement matters beyond this project: prior work in this area reports single-run
pass@1 comparisons without error bars.

### Findings

1. The static localiser is sound — 93% detection, 0 false positives, measured not asserted
2. Structural faults are rare in real LLM output — 2 in 314 analyses, two models, two circuit sets
3. Failures are overwhelmingly semantic — 133 of 153
4. Blind retry can *harm* — `retry_only` dropped Eval0 to 70% vs 90–95% elsewhere
5. No mode beats the control at n=44, against a measured 33-point variance floor
6. Static analysis is nearly free and nearly useless here; simulation feedback drives every effective repair

The value of pre-simulation structural analysis is bounded not by the technique but by the
error profile of the generator.

## Static checks

All deterministic, pre-simulation, zero LLM cost.

| Check | Catches | Compiler sees it? | Simulator sees it? |
|---|---|---|---|
| `unobserved_output` | an output the testbench never checks | no | **no** |
| `clock_never_toggled` | clock set once, never toggled — sim runs but never advances | no | rarely |
| `width_mismatch` | testbench signal width ≠ DUT port width | **no** (warning only) | sometimes |
| `undriven_input` | a DUT input never assigned | no | usually |
| `port_binding_mismatch` | port unconnected, or bound under a name the DUT lacks | partly | usually |
| `missing_fdisplay` | a sequential output never made observable | no | no |

Verilog **silently** truncates or zero-extends a width mismatch — `iverilog` exits 0 with a warning. That is why the compiler column reads "no".

## Ablation design

Five arms, so a gain can be attributed to a cause rather than assumed:

| Mode | What triggers repair |
|---|---|
| `baseline` | nothing — single shot |
| `retry_only` | nothing, but one extra generation is drawn anyway, **with zero diagnostics** |
| `compiler_only` | `iverilog` compile errors |
| `pyverilog_only` | static analysis findings |
| `hybrid` | static analysis, compiler, and simulation |

`retry_only` is the control that makes the comparison honest. Every repairing mode gets a second LLM sample that `baseline` never gets, so a gain over `baseline` alone cannot distinguish *"the feedback helped"* from *"a second attempt helped"*. **A mode must beat `retry_only` to claim its feedback works.**

## Quick start

```bash
git clone git@github.com:Sawaiz-zip/agentic-verilog-testbench.git
cd agentic-verilog-testbench
pip install -e ".[dev]"          # or: uv sync

# Icarus Verilog is required for evaluation
brew install icarus-verilog      # macOS;  apt install iverilog on Debian/Ubuntu

cp .env.example .env             # then add an API key (see below)
```

Any OpenAI-compatible provider works:

```bash
LLM_API_KEY=sk-or-...                          # OpenRouter
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_STRONG_MODEL=anthropic/claude-sonnet-4.5   # code generation, reasoning, repair
LLM_CHEAP_MODEL=openai/gpt-4o-mini             # classification, scenarios, mutants
LLM_TEMPERATURE=0.7
```

Generate a testbench from a description:

```bash
python -m pipeline run --module alu_8bit --mode hybrid
```

Run the ablation over the evaluation set:

```bash
python scripts/run_eval.py --yes --results-dir results/sweep --modules \
  alu_1bit comparator_2bit priority_encoder alu_8bit barrel_shifter_8bit bcd_to_7seg \
  dff counter_4bit shift_register fsm_sequence_detector fifo_8x8 traffic_light_fsm
```

Measure the static analyser directly (offline, free):

```bash
python scripts/run_injection_study.py
```

## Testing

```bash
pytest -q          # 195 tests, fully mocked — spends ZERO API tokens
pytest -m live     # small live-API smoke test; auto-skips without a key
```

The default suite never calls an API. Live tests are marked and skipped unless a key is present, so CI and local runs stay free.

## Project layout

```
pipeline/
  graph.py              LangGraph state machine — nodes and conditional edges
  state.py              typed graph state
  nodes/                one module per pipeline stage
  analysis/
    pyverilog_runner.py the static checks
    fault_injection.py  fault injectors for measuring the analyser
    verilog_text.py     source preparation (strips comments/strings)
    error_taxonomy.py   error classes and report structures
  standardiser/         deterministic $monitor/clock insertion (no LLM)
  eval/
    icarus.py           Eval0 compile / Eval1 simulate / Eval2 mutants
    harness.py          batch runner with budget guard and abort handling
    aggregate.py        per-mode summary tables
prompts/                Jinja templates — no inline prompt strings
scripts/                evaluation, injection study, aggregation CLIs
tests/                  195 tests; fixtures in tests/fixtures/{cmb,seq}
specs/                  design notes, one per feature increment
docs/                   architecture, walkthroughs, research log
```

## Engineering notes

A few decisions that shaped the implementation:

- **Deterministic standardisation over LLM standardisation.** Inserting `$monitor` and clock generation for sequential testbenches is a mechanical task. It is done by a Python AST pass that is idempotent and fail-safe, not by a model.
- **Prompts are templates, not strings.** Every prompt lives in `prompts/` as Jinja, so it can be diffed, reviewed and frozen before an evaluation run.
- **Every LLM call is logged** — node, model, tokens, latency, temperature — which is what makes the cost analysis possible.
- **Evidence is persisted, not recomputed.** Static findings are recorded per analysis pass, because the repair loop overwrites the report and the taxonomy cannot be reconstructed afterwards.
- **The measurement harness is tested like production code.** Building the fault-injection study surfaced eight defects in already-passing code, five of them in the analyser itself. That history is in the research log.

## Documentation

| Document | Contents |
|---|---|
| [`docs/architecture_decisions.md`](docs/architecture_decisions.md) | why LangGraph, why Pyverilog, trade-offs considered |
| [`docs/pipeline_walkthrough.md`](docs/pipeline_walkthrough.md) | node-by-node explanation |
| [`docs/results_walkthrough.md`](docs/results_walkthrough.md) | how to read the evaluation output |
| [`docs/results.md`](docs/results.md) | **consolidated findings** — all RQs, statistics, AutoBench comparison, threats to validity |
| [`docs/research-log.md`](docs/research-log.md) | dated engineering log, including defects found and corrections made |
| [`docs/roadmap.md`](docs/roadmap.md) | current status and remaining work |
| [`specs/`](specs) | design notes per feature increment |

## Context

Research project **S6.ReKI.1** at Technische Universität Ilmenau, supervised by Bing Wen. It builds on AutoBench (Qiu et al., MLCAD 2024, [arXiv:2407.03891](https://arxiv.org/abs/2407.03891)) and departs from it in three ways: a graph-based pipeline with explicit per-node failure attribution, a pre-simulation static localiser measured by fault injection, and a deterministic standardiser replacing a fragile LLM-based one.

## Licence

MIT — see [LICENSE](LICENSE).
