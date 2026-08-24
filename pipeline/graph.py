"""
LangGraph graph definition.
All pipeline steps are explicit nodes; all routing decisions are explicit conditional edges.
Constitution Principle I: no hidden control flow.
"""

from langgraph.graph import StateGraph, END

from pipeline.state import GraphState
from pipeline.config import AblationMode, PipelineConfig
from pipeline.nodes import (
    classify_node,
    gen_dut_node,
    extract_spec_node,
    gen_scenarios_node,
    gen_driver_node,
    gen_checker_node,
    merge_generation_node,
    standardise_node,
    pyverilog_analysis_node,
    error_reasoner_node,
    regenerate_node,
    repair_node,
    evaluate_node,
)
from pipeline.nodes.repair import (
    should_repair,
    should_repair_after_eval,
    after_repair,
)


def route_after_generation(state: GraphState) -> str:
    """After driver+checker both complete: SEQ circuits pass through the
    deterministic standardiser before static analysis; CMB circuits skip it."""
    if state.get("circuit_type") == "SEQ":
        return "standardise"
    return "pyverilog_analysis"


def build_graph(config: PipelineConfig) -> StateGraph:
    """
    Build and return the compiled LangGraph graph for the given ablation mode.
    The graph structure is the same for all modes; conditional edges use `config.mode`
    to decide whether to enter the repair loop.
    """
    g = StateGraph(GraphState)

    # ── Register nodes ────────────────────────────────────────────────────────
    g.add_node("classify",           classify_node)
    g.add_node("gen_dut",            gen_dut_node)
    g.add_node("extract_spec",       extract_spec_node)
    g.add_node("gen_scenarios",      gen_scenarios_node)
    g.add_node("gen_driver",         gen_driver_node)
    g.add_node("gen_checker",        gen_checker_node)
    g.add_node("merge_generation",   merge_generation_node)  # fan-in barrier
    g.add_node("standardise",        standardise_node)       # SEQ only
    g.add_node("pyverilog_analysis", pyverilog_analysis_node)
    g.add_node("error_reasoner",     error_reasoner_node)
    g.add_node("repair",             repair_node)
    g.add_node("regenerate",         regenerate_node)     # RETRY_ONLY control arm
    g.add_node("evaluate",           evaluate_node)

    # ── Entry point ───────────────────────────────────────────────────────────
    g.set_entry_point("classify")

    # ── Sequential backbone ───────────────────────────────────────────────────
    # classify (description only) → gen_dut (synthesise DUT) → extract_spec
    g.add_edge("classify",      "gen_dut")
    g.add_edge("gen_dut",       "extract_spec")
    g.add_edge("extract_spec",  "gen_scenarios")

    # ── Parallel driver + checker branches ───────────────────────────────────
    # After gen_scenarios, both gen_driver and gen_checker are launched in parallel.
    # LangGraph fans out automatically when a node has multiple outgoing edges.
    g.add_edge("gen_scenarios", "gen_driver")
    g.add_edge("gen_scenarios", "gen_checker")

    # ── Fan-in barrier: both driver + checker complete before routing ─────────
    # merge_generation runs only after BOTH gen_driver and gen_checker finish, so
    # the SEQ-vs-CMB decision (and standardise) acts on the full testbench.
    g.add_edge("gen_driver",  "merge_generation")
    g.add_edge("gen_checker", "merge_generation")

    # ── SEQ conditional: standardise before analysis (CMB skips it) ───────────
    g.add_conditional_edges(
        "merge_generation",
        route_after_generation,
        {"standardise": "standardise", "pyverilog_analysis": "pyverilog_analysis"},
    )

    g.add_edge("standardise",        "pyverilog_analysis")
    g.add_edge("pyverilog_analysis", "error_reasoner")

    # ── Repair conditional edges ──────────────────────────────────────────────
    # (1) After static analysis: PYVERILOG_ONLY / HYBRID may repair static errors.
    g.add_conditional_edges(
        "error_reasoner",
        lambda state: should_repair(state, config.mode),
        {"repair": "repair", "regenerate": "regenerate", "evaluate": "evaluate"},
    )

    # (1b) RETRY_ONLY: the resampled testbench re-enters the same post-generation
    #      path as a repaired one (SEQ re-standardises first), so the control arm
    #      differs from the repairing modes only in the absence of diagnostics.
    #      On re-entry repair_iter is 1, so should_repair routes it to evaluate.
    g.add_conditional_edges(
        "regenerate",
        after_repair,
        {
            "standardise": "standardise",
            "pyverilog_analysis": "pyverilog_analysis",
            "evaluate": "evaluate",
        },
    )

    # (2) After a repair: re-analyse the regenerated testbench (SEQ re-standardises
    #     first), or stop (oscillation / budget exhausted) by going to evaluate.
    g.add_conditional_edges(
        "repair",
        after_repair,
        {
            "standardise": "standardise",
            "pyverilog_analysis": "pyverilog_analysis",
            "evaluate": "evaluate",
        },
    )

    # (3) After evaluation: COMPILER_ONLY repairs compile failures; HYBRID repairs
    #     compile OR simulation failures; otherwise terminate.
    g.add_conditional_edges(
        "evaluate",
        lambda state: should_repair_after_eval(state, config.mode),
        {"repair": "repair", "END": END},
    )

    return g.compile()


def default_graph():
    """No-arg entry point for LangGraph Studio (hybrid mode)."""
    return build_graph(PipelineConfig(mode=AblationMode.HYBRID))
