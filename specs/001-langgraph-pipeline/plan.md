# Implementation Plan: LangGraph Verilog Testbench Generation Pipeline

**Branch**: `001-langgraph-pipeline` | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)

## Summary

Build a LangGraph state-machine pipeline that takes a natural-language circuit description + golden DUT Verilog and produces a validated testbench. The pipeline adds a Pyverilog-based pre-simulation error-localisation layer and a deterministic `$fdisplay` standardiser, enabling structured LLM repair before falling back to simulation feedback. Primary contribution is the pipeline architecture and per-node behaviour analysis, not peak benchmark accuracy.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `langgraph`, `anthropic`, `pyverilog`, `jinja2`, `pytest`
**Storage**: JSON files per run (results/), no database
**Testing**: pytest (unit + integration)
**Target Platform**: macOS / Linux (single machine, CLI)
**Project Type**: research CLI tool
**Performance Goals**: full pipeline run per module < 60 s wall-clock; Pyverilog analysis < 2 s per file
**Constraints**: Anthropic free-tier rate limits; temperature=0 on all LLM nodes
**Scale/Scope**: 156 VerilogEval modules; 5-module smoke set for fast iteration

## Constitution Check

| Principle | Status |
|---|---|
| I. Graph-First | All steps are LangGraph nodes — PASS |
| II. Prompt Externalisation | All prompts go in `prompts/*.j2` — PASS |
| III. LLM Logging | Shared `llm_call()` wrapper required before any node can call the API — PASS |
| IV. Temperature 0 | Declared in every node's call to `llm_call()` — PASS |
| V. CMB Before SEQ | Phase 3 (CMB) fully gates Phase 4 (SEQ) — PASS |
| VI. Deterministic Standardiser | Python AST pass only; no LLM path — PASS |
| VII. Static Before Simulation | Pyverilog node runs before `iverilog` eval node — PASS |
| VIII. Model Routing | Haiku for classify/scenarios; Sonnet for everything else — PASS |
| IX. Reproducibility | UUID run_id; held-out 80% split; prompts frozen before final eval — PASS |
| X. RQ Traceability | Every node docstring will cite its RQ — PASS |

## Project Structure

```text
ResearchProject/
├── pipeline/                     # Main package
│   ├── __init__.py
│   ├── graph.py                  # LangGraph graph definition (nodes + edges)
│   ├── state.py                  # GraphState TypedDict
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── classify.py           # Node 1a: CMB/SEQ classification (Haiku)
│   │   ├── extract_spec.py       # Node 1b: JSON spec extraction (Sonnet)
│   │   ├── gen_scenarios.py      # Node 1c: scenario list (Haiku)
│   │   ├── gen_driver.py         # Node 1d: Verilog driver generation (Sonnet)
│   │   ├── gen_checker.py        # Node 1e: Python checker generation (Sonnet)
│   │   ├── standardise.py        # Node 4: deterministic $fdisplay inserter (no LLM)
│   │   ├── pyverilog_analysis.py # Node 2: Pyverilog + Verible fallback
│   │   ├── error_reasoner.py     # Node 3: LLM error reasoning (Sonnet)
│   │   ├── repair.py             # Node 5: repair loop router
│   │   └── evaluate.py           # Node 6: Icarus Verilog eval (Eval0/1/2)
│   ├── llm.py                    # Shared LLM wrapper (logging, backoff, routing)
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── pyverilog_runner.py   # Pyverilog AST + dataflow orchestration
│   │   ├── verible_runner.py     # Verible fallback parser
│   │   └── error_taxonomy.py     # Error type constants + PyverilogReport dataclass
│   ├── standardiser/
│   │   ├── __init__.py
│   │   └── fdisplay_inserter.py  # Python AST pass for $fdisplay insertion
│   ├── eval/
│   │   ├── __init__.py
│   │   ├── icarus.py             # iverilog / vvp subprocess wrapper
│   │   └── mutant_gen.py         # LLM-based mutant generation (Haiku)
│   └── config.py                 # AblationMode enum, PipelineConfig dataclass
│
├── prompts/                      # Jinja2 prompt templates
│   ├── classify_circuit.j2
│   ├── extract_spec.j2
│   ├── gen_scenarios.j2
│   ├── gen_driver.j2
│   ├── gen_checker.j2
│   ├── error_reasoner.j2
│   ├── repair_driver.j2
│   └── gen_mutant.j2
│
├── tests/
│   ├── unit/
│   │   ├── test_classify.py
│   │   ├── test_pyverilog_runner.py
│   │   ├── test_fdisplay_inserter.py
│   │   ├── test_error_taxonomy.py
│   │   └── test_icarus.py
│   ├── integration/
│   │   ├── test_cmb_pipeline.py  # End-to-end on 5 smoke modules
│   │   └── test_repair_loop.py   # Inject error, verify repair
│   └── fixtures/
│       ├── cmb/                  # Hand-picked combinational Verilog DUTs + NL descriptions
│       └── seq/                  # Hand-picked sequential Verilog DUTs
│
├── data/
│   └── verilog_eval/             # VerilogEval dataset (downloaded separately)
│
├── results/                      # Per-run JSON output (git-ignored)
│
├── scripts/
│   ├── run_smoke.sh              # Run pipeline on 5-module smoke set
│   └── run_eval.sh               # Full 156-module evaluation
│
├── pyproject.toml
├── .env.example                  # ANTHROPIC_API_KEY placeholder
├── CLAUDE.md                     # Project context (existing)
├── docs/research-log.md                   # Progress tracker (existing)
└── specs/
    └── 001-langgraph-pipeline/
        ├── spec.md               # This feature spec
        ├── plan.md               # This file
        └── tasks.md              # Generated by /speckit-tasks
```

**Structure Decision**: Single Python package (`pipeline/`) with clear sub-modules. No web or mobile layer. CLI entry point via `python -m pipeline run`. Results are JSON files, not a database.

## Phase Breakdown

### Phase 0 — Foundation (Weeks 1–2, May 2026)
Shared infrastructure that all nodes depend on. Nothing else can start until this is done.

- Python project setup (`pyproject.toml`, `uv`, env)
- `GraphState` TypedDict (`pipeline/state.py`)
- Shared LLM wrapper with logging (`pipeline/llm.py`)
- `PipelineConfig` + `AblationMode` enum (`pipeline/config.py`)
- Empty LangGraph graph skeleton (`pipeline/graph.py`) — nodes registered but pass-through
- pytest harness + fixture directory structure

### Phase 1 — CMB Generation (Weeks 3–6, May–Jun 2026)
Core combinational testbench generation without repair or static analysis.

- Nodes: classify → extract_spec → gen_scenarios → gen_driver ‖ gen_checker → evaluate
- Jinja2 prompts for all 5 generation nodes
- Icarus Verilog wrapper (Eval0 + Eval1)
- Mutant generator for Eval2
- End-to-end integration test on 5 CMB smoke modules

**Gate**: Eval0 ≥ 80% and Eval1 ≥ 50% on smoke set before Phase 2.

### Phase 2 — Pyverilog Layer (Weeks 5–9, Jun 2026)
The primary research contribution.

- Pyverilog runner (AST port-binding check, sensitivity-list check, dataflow check)
- Verible fallback runner
- `PyverilogReport` dataclass + error taxonomy constants
- Error reasoner node (Sonnet) — Pyverilog report → structured error list
- Unit tests for Pyverilog runner with hand-crafted buggy testbenches
- Error precision/recall measurement on 20-module hand-labelled dev set

### Phase 3 — Repair Loop (Weeks 10–11, Jun–Jul 2026)

- Repair router node with oscillation detection
- Conditional edge: `should_repair()` function
- `repair_driver.j2` prompt
- Integration test: inject known error, verify repair within 2 iterations
- Four ablation modes wired via `AblationMode` config flag

### Phase 4 — SEQ Support (Weeks 12–13, Jul 2026)

- Deterministic `$fdisplay` inserter (Python AST pass, no LLM)
- SEQ path in LangGraph (standardiser node before Pyverilog)
- SEQ smoke set (5 modules from VerilogEval SEQ subset)
- `circuit_type=SEQ` routing in conditional edge

**Gate**: Full CMB pipeline at production quality before any SEQ node is written.

### Phase 5 — Evaluation & Analysis (Weeks 14–16, Jul–Aug 2026)

- Full 156-module VerilogEval run across all 4 ablation modes
- Aggregate results script → `results/summary.json`
- Per-node failure attribution analysis
- Token cost analysis per mode
- Error taxonomy frequency table (bootstrapped on dev set)

### Phase 6 — Write-Up (Weeks 17–20, Aug–Sep 2026)

- Final report in LaTeX (`expose.tex` extended to full paper)
- Figures: pipeline diagram, ablation comparison table, failure attribution breakdown
- Submission by 2026-09-01

## Complexity Tracking

No constitution violations. The project naturally fits a single-package structure with a CLI entry point.
