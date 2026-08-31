# Agentic Verilog Testbench Generation

**A multi-agent pipeline that writes Verilog testbenches from natural language, finds structural faults *before* simulation, and repairs them from structured feedback.**

Built on LangGraph (orchestration), Pyverilog (static analysis) and Icarus Verilog (evaluation).

[![tests](https://img.shields.io/badge/tests-201%20passed-brightgreen)]()
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

**280 pipeline runs** across four sweeps, plus an offline fault-injection study.
Full detail and reproduction commands in [`docs/results.md`](docs/results.md).
Every figure below is checked against the raw JSON by `scripts/audit_report_figures.py`.

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

| Sweep | Model | Analyses | Checks actually ran | Runs with a finding |
|---|---|---|---|---|
| 12 project circuits | `claude-sonnet-4.5` | 82 | 75 | **0 / 60** |
| 12 project circuits | `gpt-4o-mini` | 79 | 51 | **1 / 60** |
| 20 VerilogEval circuits | `gpt-4o-mini` | 153 | 64 | **1 / 100** |
| 20 VerilogEval circuits | `claude-sonnet-4.5` | 120 | 72 | **1 / 60** |

**3 runs with findings in 262 analyses.** Quote that denominator, not 434 — Pyverilog could
not parse 172 of the files and the pipeline fell back to Verible, which returns a syntax
verdict and runs **none** of the six checks while still recording `parse_ok`. The null result
holds over the analyses that actually ran and is silent about the rest.

Both a weak and a strong model produce structurally well-formed testbenches. Substituting
`claude-sonnet-4.5` for `gpt-4o-mini` on the same 20 benchmark circuits moved Eval1 by 25
points and left the structural yield unchanged — **89% of all failures across the four sweeps
are semantic** (171 of 192) and require simulation by definition.

### Ablation, pooled (n=44 per mode)

| mode | Eval1 | 95% CI | tokens vs baseline |
|---|---|---|---|
| `pyverilog_only` | 20.5% | [11.2, 34.5] | −2% |
| `baseline` | 27.3% | [16.3, 41.8] | — |
| `retry_only` | 29.5% | [18.2, 44.2] | +29% |
| `compiler_only` | 34.1% | [21.9, 48.9] | +6% |
| **`hybrid`** | **40.9%** | [27.7, 55.6] | +50% |

### The control arm, and what it settles

`retry_only` gets a second generation attempt with **zero diagnostics**. Across both samples
it fails to beat `baseline` at all — McNemar **p = 1.000** in each. *The extra attempt on its
own is worth nothing.* Since `hybrid` also receives that attempt, whatever separates them is
the diagnosis.

On the benchmark circuits with the strong model:

| mode | Eval0 | Eval1 |
|---|---|---|
| `baseline` | 95% | 25% |
| `retry_only` | 100% | 30% |
| **`hybrid`** | **100%** | **50%** |

| comparison | matched | hybrid wins | control wins | McNemar |
|---|---|---|---|---|
| ablation | 44 | 6 | 1 | p = 0.125 |
| benchmark, strong model | 20 | 5 | 1 | p = 0.219 |
| **stratified** | **64** | **11** | **2** | **p = 0.023** |

⚠️ **Read that last row carefully.** It is *post hoc* — the sweep was run, `hybrid` was seen
leading, the control was added, and the samples pooled afterwards. It does not survive
Bonferroni for the 11 comparisons made, and the strata differ in generator and circuits. The
claim is that the evidence **points one way rather than none**, not that the effect is
established.

Decomposing `hybrid`'s ablation lead shows why significance is hard: of its 18 passes, **3
were rescued by a repair** and 15 passed first time against `baseline`'s 12 from an identical
process. The mechanism is worth ~7 points; the rest is variance. Arms taking an identical code
path scored 33 points apart at n=12 and 6.8 at n=44 — that is the floor any claim must clear.

### Findings

1. The static localiser is sound — 93% detection, 0 false positives, measured not asserted
2. Structural faults are rare in real LLM output — 3 runs in 262 analyses, two models, two circuit sets
3. Failures are overwhelmingly semantic — 89% across all four sweeps
4. Blind retry is worth nothing (p = 1.000 both samples), and *harms* compilation when the generator is weak
5. Informed repair leads the control 11–2 across 64 matched circuits — suggestive, uncorrected, not established
6. Repair succeeds rarely and fails in two distinct ways — see below
7. Static analysis is nearly free and nearly useless here; simulation feedback drives every effective repair

The value of pre-simulation structural analysis is bounded not by the technique but by the
error profile of the generator.

### Why repairs fail

23 runs performed a repair informed by a diagnosis. **3 passed — 13%.** Of the 20 failures:

- **7** regenerated a testbench that failed the **identical** scenario set — the diagnosis was not acted on
- **13** exhausted the iteration budget with a **different** error signature every time. Across 14 multi-iteration runs, **no signature ever repeated** — each repair trades one failing corner case for another and never converges

**10 of 17 finished one or two scenarios short** of passing. The testbenches are not
collapsing; they are right about the interface, right about most behaviour, and wrong about a
corner case. Prior work reports that debugging helps and does not characterise when it doesn't.

### Eval2 is at ceiling — and it is not the mutants' fault

Eval2 sits at 324/335 (97%) and discriminates nothing. The obvious explanation was tested and
**rejected**:

| what changed | caught |
|---|---|
| our circuits, original mutants | 96.7% |
| our circuits, better mutants (strong model, AutoBench's prompt, equivalents filtered) | **97.4%** |
| **benchmark circuits**, AutoBench's own published mutants | **53.8%** weak / **66.7%** strong |

Better mutants moved it one point; different circuits moved it forty-four. **The fixture
circuits are too small for a bug to hide in** — `dff` has one input bit. Pre-registered
criteria for that pilot are in [`specs/012-mutant-quality/PILOT_CRITERIA.md`](specs/012-mutant-quality/PILOT_CRITERIA.md),
committed before any mutant was generated.

### Against AutoBench

Their published mutants and evaluation rule, on the hardest quintile of their own benchmark:

| | AutoBench (156) | AutoBench (SEQ) | This work (20 hardest, 75% SEQ) |
|---|---|---|---|
| Eval0 | 95.71% | 97.33% | 100% |
| Eval1 | 51.47% | 37.07% | **50%** |
| Eval2 (their ≥80% rule) | 44.81% | 26.00% | **20%** |

**No ranking is claimed.** The generators are two years apart, twenty circuits give a Wilson
interval of 30–70%, and AutoBench has scenario-checking and reboot mechanisms this pipeline
lacks. The defensible statement is *in the same range*.

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

The first three sweeps run all five arms. The fourth runs `baseline`, `retry_only` and `hybrid` — `retry_only` was kept deliberately, because dropping it would have reproduced exactly the confound this project criticises in prior work.

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
pytest -q          # 201 tests, fully mocked — spends ZERO API tokens
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
scripts/
  run_eval.py           batch sweep runner (budget guard, abort handling)
  run_injection_study.py  fault-injection measurement
  analyse_results.py    cross-sweep statistics
  audit_report_figures.py  recomputes 28 report figures from raw JSON and diffs them
tests/                  201 tests; fixtures in tests/fixtures/{cmb,seq}
specs/                  design notes, one per feature increment
docs/                   architecture, walkthroughs, research log
  learn/                8-part series explaining the project from zero background
```

## Engineering notes

A few decisions that shaped the implementation:

- **Deterministic standardisation over LLM standardisation.** Inserting `$monitor` and clock generation for sequential testbenches is a mechanical task. It is done by a Python AST pass that is idempotent and fail-safe, not by a model.
- **Prompts are templates, not strings.** Every prompt lives in `prompts/` as Jinja, so it can be diffed, reviewed and frozen before an evaluation run.
- **Every LLM call is logged** — node, model, tokens, latency, temperature — which is what makes the cost analysis possible.
- **Evidence is persisted, not recomputed.** Static findings are recorded per analysis pass, because the repair loop overwrites the report and the taxonomy cannot be reconstructed afterwards.
- **The measurement harness is tested like production code.** Building the fault-injection study surfaced eight defects in already-passing code, five of them in the analyser itself. That history is in the research log.

## Documentation

### Start here if the project is new to you

[`docs/learn/`](docs/learn) is an eight-part series written for a reader with no hardware or
circuits background. Read it in order; each part assumes only the ones before it.

| | Document | Covers |
|---|---|---|
| 01 | [Hardware and Verilog](docs/learn/01-hardware-and-verilog.md) | modules, ports, `wire` vs `reg`, clocks, reset — explained against real fixtures from this repo |
| 02 | [Verification and testbenches](docs/learn/02-verification-and-testbenches.md) | what a testbench is, structural vs semantic faults, Eval0/1/2, mutants |
| 03 | [Tools and stack](docs/learn/03-tools-and-stack.md) | Pyverilog, Icarus, Verible, LangGraph — what each does and cannot do |
| 04 | [AutoBench explained](docs/learn/04-autobench-explained.md) | the seed paper: stages, self-enhancement, numbers, the missing control |
| 05 | [Our pipeline](docs/learn/05-our-pipeline.md) | node by node, with the reasoning for each choice |
| 06 | [Experiments and results](docs/learn/06-experiments-and-results.md) | both studies, why the injection study comes first, all four sweeps |
| 07 | [Us vs AutoBench](docs/learn/07-comparison.md) | the honest comparison, and why the Eval2 numbers are not comparable |
| 08 | [Presentation Q&A](docs/learn/08-viva-questions.md) | anticipated questions with answers, basics through to the uncomfortable ones |

### Reference

| Document | Contents |
|---|---|
| [`report.tex`](report.tex) / `report.pdf` | the full research report — 46 pages, all figures audited against raw data |
| [`docs/architecture_decisions.md`](docs/architecture_decisions.md) | why LangGraph, why Pyverilog, trade-offs considered |
| [`docs/pipeline_walkthrough.md`](docs/pipeline_walkthrough.md) | node-by-node explanation |
| [`docs/results_walkthrough.md`](docs/results_walkthrough.md) | how to read the evaluation output |
| [`docs/results.md`](docs/results.md) | **consolidated findings** — all RQs, statistics, AutoBench comparison, threats to validity |
| [`docs/research-log.md`](docs/research-log.md) | dated engineering log, including defects found and corrections made |
| [`docs/roadmap.md`](docs/roadmap.md) | current status and remaining work |
| [`specs/`](specs) | design notes per feature increment |
| [`specs/012-mutant-quality/PILOT_CRITERIA.md`](specs/012-mutant-quality/PILOT_CRITERIA.md) | pre-registered criteria for the Eval2 mutant pilot, committed before generation |

## Context

Research project **S6.ReKI.1** at Technische Universität Ilmenau, supervised by Bing Wen. It builds on AutoBench (Qiu et al., MLCAD 2024, [arXiv:2407.03891](https://arxiv.org/abs/2407.03891)) and departs from it in four ways: a graph-based pipeline with per-call telemetry and a repair-feedback breakdown, a pre-simulation static localiser measured by fault injection rather than asserted, a deterministic standardiser replacing a fragile LLM-based one, and a no-diagnostics control arm that separates the value of a diagnosis from the value of a retry.

*(The original plan claimed per-node attribution of where failures **originate**. The instrumentation records where failure is **detected**, which is not the same thing; the report states what was delivered instead.)*

## Licence

MIT — see [LICENSE](LICENSE).
