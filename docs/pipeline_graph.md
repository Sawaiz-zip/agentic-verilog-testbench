# LangGraph Pipeline — Visual Diagram

> Reflects the current graph in `pipeline/graph.py` (nodes, parallel branches,
> the SEQ-only `standardise` step, and both repair re-entry paths). Companion to
> `docs/pipeline_walkthrough.md` (node-by-node explanation).

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([__start__])
	classify(classify)
	gen_dut(gen_dut)
	extract_spec(extract_spec)
	gen_scenarios(gen_scenarios)
	gen_driver(gen_driver)
	gen_checker(gen_checker)
	merge_generation{{merge_generation<br/>fan-in barrier}}
	standardise(standardise<br/>SEQ only, no LLM)
	pyverilog_analysis(pyverilog_analysis<br/>no LLM)
	error_reasoner(error_reasoner)
	repair(repair)
	evaluate(evaluate<br/>Eval0/1/2)
	__end__([__end__])

	__start__ --> classify;
	classify --> gen_dut;
	gen_dut --> extract_spec;
	extract_spec --> gen_scenarios;
	gen_scenarios --> gen_driver;
	gen_scenarios --> gen_checker;
	gen_driver --> merge_generation;
	gen_checker --> merge_generation;
	merge_generation -->|SEQ| standardise;
	merge_generation -->|CMB| pyverilog_analysis;
	standardise --> pyverilog_analysis;
	pyverilog_analysis --> error_reasoner;
	error_reasoner -.->|errors + iters left| repair;
	error_reasoner -.->|clean / exhausted| evaluate;
	repair -.->|SEQ| standardise;
	repair -.->|CMB| pyverilog_analysis;
	repair -.->|give up| evaluate;
	evaluate -.->|compile/sim fail, mode-gated| repair;
	evaluate --> __end__;

	classDef default fill:#f2f0ff,line-height:1.2
	classDef nollm fill:#fef9e7
	classDef eval fill:#fadbd8
	class standardise,pyverilog_analysis,merge_generation nollm
	class evaluate eval
```

**Notes**
- `gen_driver` and `gen_checker` run as **parallel branches**; `merge_generation`
  is a fan-in barrier that waits for both.
- `standardise` runs **only for SEQ** circuits (CMB skips straight to analysis).
- Two repair entry points: from `error_reasoner` (static/Pyverilog errors) and from
  `evaluate` (compile/simulation failure) — the latter is **mode-gated** (only
  `compiler_only` and `hybrid` re-enter on simulation feedback).
- `repair` regenerates the testbench and routes back into analysis, not straight to
  evaluation, so the fix is re-checked before grading.
- Deterministic nodes (yellow) use **no LLM**: `merge_generation`,
  `standardise`, `pyverilog_analysis` (and `evaluate` runs Icarus Verilog).

> The `pipeline_graph.png` in this folder is an **older** render (pre-`gen_dut`); the
> Mermaid above is the source of truth. Regenerate the PNG from this block if needed.