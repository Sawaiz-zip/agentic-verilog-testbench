# S6.ReKI.1 — LLM-Driven Verilog Testbench Generation with Pyverilog-Based Early Error Localization

**Student:** Muhammad Sawaiz Naveed | **Supervisor:** Bing Wen | **University:** TU Ilmenau | **Deadline:** Sept 1, 2026

---

## What This Project Does

Writing testbenches — the code that checks whether a hardware circuit is correct — is slow and tedious. This project builds a pipeline that does it automatically using an AI (Claude), but with a key twist:

Instead of the usual approach of *generate → simulate → hope for the best*, we add a **smart pre-simulation checker** (Pyverilog) that reads the generated testbench and spots structural errors immediately — wrong port connections, undriven inputs, missing output observers — before wasting time on a full simulation. The AI then gets precise, actionable feedback and repairs its own output. Only after the testbench passes static analysis does it go to the simulator.

The whole pipeline is built as a **LangGraph graph**: every step is a named node, every routing decision is a visible edge. Nothing is hidden.

---

## The Problem (in plain English)

LLMs can write Verilog testbenches from a description, but the output is often *syntactically valid but functionally wrong* — the simulator compiles it, but the testbench fails to test the circuit correctly because:

- Ports are wired to the wrong signals
- Some inputs are never driven
- Some outputs are never checked
- The clock sensitivity list is wrong
- Print statements (`$fdisplay`) are missing so simulation output is empty

The standard fix is to run the simulator, read the error, and try again. This is slow and the errors are vague. **We instead detect these errors in milliseconds using static analysis, before any simulation runs.**

---

## How It Works

```
INPUT: Plain-English description (golden DUT optional, for evaluation only)
         │
         ▼
[1] CLASSIFY — combinational (CMB) or sequential (SEQ)?           [cheap model]
         │
         ▼
[2] GEN DUT — synthesise the design-under-test from the description   [strong]
         │
         ▼
[3] EXTRACT SPEC — ports, behaviour, timing (structured JSON)         [strong]
         │
         ▼
[4] GENERATE SCENARIOS — the test cases to cover                  [cheap model]
         │
         ├──────────────────────────┐
         ▼                          ▼
[5a] GENERATE DRIVER          [5b] GENERATE CHECKER
     (Verilog testbench) [strong]   (Python checker) [strong]
         │                          │
         └────────── MERGE ─────────┘   (fan-in barrier)
         │
         ▼  (SEQ only)
[6] STANDARDISE — insert missing $monitor / clock toggle   [Python, no LLM]
         │
         ▼
[7] PYVERILOG ANALYSIS — port bindings, sensitivity, dataflow  [Pyverilog / Verible]
         │
         ▼
[8] ERROR REASONER — turn findings into actionable fixes (skipped if clean)  [strong]
         │
         ├── errors + iterations left ──▶ [9] REPAIR (regenerate, best-so-far) ──▶ re-analyse
         │
         ▼
[10] EVALUATE — Eval0 compile → Eval1 vs correct DUT → Eval2 vs mutants  [Icarus Verilog]
         │
         ▼
OUTPUT: Testbench + per-run JSON (errors, tokens, repair iterations, Eval0/1/2)
```

> Model routing: a **cheap** model (e.g. `gpt-4o-mini`) for classify/scenarios/mutants;
> a **strong** model (e.g. `claude-sonnet-4.5`) for DUT/spec/driver/checker/reasoning/repair.
> Deterministic nodes (standardise, pyverilog_analysis, merge, evaluate) use no LLM.

---

## What Makes This Different from Prior Work

| | AutoBench (baseline) | This project |
|---|---|---|
| Error detection | Simulator errors only (vague) | **Pyverilog static analysis** (precise, pre-simulation) |
| `$fdisplay` insertion | LLM-based (fragile) | **Deterministic Python AST pass** (100% reliable) |
| Failure attribution | Not available | **Per-node failure stage logged** for every run |
| Model tested | GPT-4 only | Claude Sonnet + gpt-4o-mini (provider-agnostic) |
| Cost analysis | Not reported | **Token cost per module per ablation mode** |
| Ablation study | None | 5 modes incl. a no-diagnostics control: baseline / retry-only / compiler-only / pyverilog-only / hybrid |

---

## Project Structure

```
pipeline/          Main package
  config.py        AblationMode enum + PipelineConfig
  state.py         GraphState TypedDict (all pipeline data)
  llm.py           Shared LLM wrapper (logging, backoff, configurable temperature, LangSmith tracing)
  graph.py         LangGraph graph definition
  nodes/           One file per pipeline node
  analysis/        Pyverilog runner + Verible fallback + error taxonomy
  standardiser/    Deterministic $fdisplay inserter (no LLM)
  eval/            Icarus Verilog wrapper + mutant generator

prompts/           Jinja2 prompt templates (one per LLM node)
tests/             pytest unit + integration tests + fixtures
scripts/           run_eval.py (ablation runner), aggregate_results.py, aggregate_repeats.py
specs/             Spec-kit planning documents (constitution, spec, plan, tasks)
data/verilog_eval/ VerilogEval dataset (download separately)
results/           Per-run JSON output (git-ignored)
```

---

## Setup

```bash
# 1. Clone the repo
git clone <repo-url>
cd ResearchProject

# 2. Install dependencies (requires uv or pip)
uv sync --extra dev
# or: pip install -e ".[dev]"

# 3. Configure your LLM provider (any OpenAI-compatible provider works)
cp .env.example .env
# Option A — OpenRouter (current, paid — best model quality):
#   LLM_API_KEY=sk-or-...   (get from openrouter.ai/keys)
#   LLM_BASE_URL=https://openrouter.ai/api/v1
#   LLM_STRONG_MODEL=anthropic/claude-sonnet-4.5
#   LLM_CHEAP_MODEL=openai/gpt-4o-mini
#   LLM_TEMPERATURE=0.7
# Option B — Groq free tier (no credit card):
#   LLM_API_KEY=gsk_...   LLM_BASE_URL=https://api.groq.com/openai/v1
#   LLM_CHEAP_MODEL=LLM_STRONG_MODEL=llama-3.3-70b-versatile
# Option C — Anthropic direct:  ANTHROPIC_API_KEY=sk-ant-...
# Optional observability:  LANGSMITH_TRACING=true  LANGSMITH_PROJECT=S6-ReKI-1

# 4. Verify tools are available
iverilog --version   # Icarus Verilog (brew install icarus-verilog)
python -c "import pyverilog; print('pyverilog ok')"
python -m pipeline --help
```

---

## Running

The pipeline runs from a **natural-language description alone** — it generates
its own DUT (Design Under Test) from the description, then generates and
evaluates a testbench for it. A golden DUT is optional and used only for
benchmark evaluation.

```bash
# Description only (user flow): DUT is generated from the description
python -m pipeline run --module half_adder --mode hybrid
python -m pipeline run --nl my_circuit.txt --module my_circuit --mode hybrid

# Benchmark mode: golden DUT supplied → used for evaluation only
python -m pipeline run --module Prob005_notgate --mode hybrid   # from VerilogEval
python -m pipeline run --nl desc.txt --dut golden.v --module m  # explicit golden DUT

# Every run prints a human-readable summary (scenarios passed, Eval0/1/2,
# tokens, wall time, status) and writes results/<run_id>.json.

# Configurable sampling temperature (default 0.7; the pipeline is robust to >0)
LLM_TEMPERATURE=0.9 python -m pipeline run --module half_adder --mode hybrid

# Ablation over the evaluation set (12 circuits × 5 modes = 60 runs per repeat)
python scripts/run_eval.py --modules alu_1bit comparator_2bit priority_encoder \
  alu_8bit barrel_shifter_8bit bcd_to_7seg \
  dff counter_4bit shift_register \
  fsm_sequence_detector fifo_8x8 traffic_light_fsm \
  --yes --results-dir results/final_hard_r1

# VerilogEval is wired up but NOT part of this project's evaluation (not funded):
#   python scripts/run_eval.py --modules verilogeval:10 --yes --results-dir results/vle10

# Aggregate a results folder into a per-mode comparison table
python scripts/aggregate_results.py --results-dir results/my_sweep
```

### Testing

```bash
pytest -q            # full suite, fully mocked — spends ZERO API tokens
pytest -m live       # small live-API smoke test; auto-skips without an API key
```

---

## Ablation Modes

| Mode | What triggers LLM repair |
|---|---|
| `baseline` | Nothing — single shot, no repair |
| `retry_only` | **Nothing — but one extra `gen_driver` sample is drawn anyway, with zero diagnostics.** The control arm. |
| `compiler_only` | Only `iverilog` compile errors |
| `pyverilog_only` | Only Pyverilog static analysis errors |
| `hybrid` | Both — Pyverilog first, then compiler |

Every repairing mode receives a second LLM generation that `baseline` never gets, so a gain
over `baseline` alone cannot distinguish "the feedback helped" from "a second sample helped".
`retry_only` isolates that: a mode must beat **`retry_only`** to claim its feedback works.

---

## Research Questions

- **RQ1** — What error categories appear most often in LLM-generated testbenches, and which are detectable without simulation?
- **RQ2** — How well does Pyverilog's AST/dataflow analysis localize testbench errors before simulation?
- **RQ3** — Can an LLM guided by Pyverilog output effectively repair testbench errors? How does this compare to compiler-only feedback?
- **RQ4** — What is the cost–quality tradeoff of Pyverilog-guided repair vs compiler-only repair?

---

## Implementation Status (2026-08-24)

| Phase | Focus | Status |
|---|---|---|
| 0 — Setup | Env, deps, Pyverilog smoke test | ✅ Done |
| 1 — Generation | CMB pipeline end-to-end | ✅ Done |
| 2 — Pyverilog | Static analysis layer | ✅ Done |
| 3 — Repair + SEQ | Repair loop + sequential support | ✅ Done |
| 4 — Evaluation | Ablation sweeps + analysis | 🟡 Re-planned after an audit of the first sweeps |
| 5 — Writing | Final report (deadline Sept 1 2026) | ⚪ Not started |

### First results, and why they are not being reported

An 8-fixture × 4-mode sweep was run on 2026-07-15 and appeared to show `pyverilog_only`
beating `baseline` at both temperatures. Auditing it before building further found that
result to be unsound:

- **All 5 combinational fixtures pass in every mode at both temperatures** — 40 of the 64
  runs are constant. Every point of variance comes from 3 sequential circuits, and the
  mode ordering flips between temperatures.
- **The static layer fired exactly one check, and it was a false positive.** Re-running the
  analyser over all 32 saved testbenches produced 3 findings, all `missing_fdisplay`, all
  spurious: the check demanded the output appear inside a `$display` argument list, while a
  self-checking testbench observes it via `if (q === ...)`. All 5 static-triggered repairs
  in both sweeps came from this one bug.
- **No control for the extra sample.** `pyverilog_only` was effectively `baseline` plus one
  regeneration, and nothing separated the feedback from the resample.

All four defects are fixed (see `specs/008-control-arm-and-static-evidence/NOTES.md`). After
the fix the static layer reports **nothing** on those 8 fixtures — the checks are not weak so
much as untestable there: four of five cannot fire on 8–17 line circuits with 2–4 unambiguous
ports. The evaluation is therefore being re-run on **12 circuits (6 purpose-built hard) × 5
modes × 2 repeats at temp 0.7**, alongside an offline error-injection study that measures the
localiser directly. Full detail in [`PROGRESS.md`](PROGRESS.md) and [`TODO.md`](TODO.md).

**Active LLM provider:** OpenRouter (paid) — `claude-sonnet-4.5` (strong) + `gpt-4o-mini`
(cheap). Provider-agnostic via the OpenAI-compatible abstraction (Groq/Anthropic/OpenAI also work).
**Tests:** 88 passed, 3 skipped (offline).

---

## Dependencies

- [LangGraph](https://github.com/langchain-ai/langgraph) — graph-based pipeline orchestration
- [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) — Claude API
- [Pyverilog](https://github.com/PyHDI/Pyverilog) — Verilog AST + dataflow analysis
- [Icarus Verilog](http://iverilog.icarus.com/) — Verilog simulator (install separately)
- [Jinja2](https://jinja.palletsprojects.com/) — prompt templating
- [pytest](https://pytest.org/) — testing

---

## References

- Qiu et al. 2024 — AutoBench: LLM testbench generation (arXiv:2407.03891) — the seed paper
- Liu et al. 2023 — VerilogEval: 156-problem benchmark (arXiv:2309.07544) — evaluation dataset
- Takamaeda 2015 — Pyverilog: Python toolkit for Verilog analysis — core static analysis tool
