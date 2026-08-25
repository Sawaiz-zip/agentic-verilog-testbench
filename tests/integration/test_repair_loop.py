"""
T016/T017 — repair loop through the full LangGraph, fully offline.
Covers: success-within-budget, BASELINE never repairs, oscillation → oscillated,
exhaustion → exhausted_iters, repair_iter <= max always, and no fan-in deadlock
on loop re-entry (repair → pyverilog_analysis).
"""

import importlib

from pipeline.config import AblationMode, PipelineConfig
from pipeline.graph import build_graph

_NODE_MODS = [
    "pipeline.nodes.classify", "pipeline.nodes.gen_dut", "pipeline.nodes.extract_spec",
    "pipeline.nodes.gen_scenarios", "pipeline.nodes.gen_driver",
    "pipeline.nodes.gen_checker", "pipeline.nodes.error_reasoner",
    "pipeline.nodes.repair", "pipeline.eval.mutant_gen",
]

_DUT = "module top_module(input a, input b, output sum, output cout);\n" \
       "  assign sum = a ^ b; assign cout = a & b;\nendmodule\n"
_DRIVER = "module testbench;\n  reg a,b; wire sum,cout;\n" \
          "  top_module uut(.a(a),.b(b),.sum(sum),.cout(cout));\n" \
          "  initial begin a=0;b=0;#10; $display(\"PASS: zero\"); $finish; end\nendmodule\n"

_CANNED = {
    "classify": '{"circuit_type": "CMB"}',
    "gen_dut": _DUT,
    "extract_spec": '{"ports": {"inputs": [], "outputs": []}, "timing": "combinational"}',
    "gen_scenarios": '[{"name": "zero", "inputs": {}, "expected": {}}]',
    "gen_driver": _DRIVER,
    "gen_checker": "def check(o):\n    return True\n",
    "error_reasoner": "[]",
    "gen_mutant": _DUT,
    "repair": _DRIVER + "\n// repaired\n",
}


def _install_llm(monkeypatch, responses, counter=None):
    """Patch llm_call in every node module. If `counter` given, the repair
    response is made unique per call (to avoid driver-identity oscillation)."""
    def fake(*, node, model, prompt, run_id, max_tokens=4096, max_retries=3,
            temperature=None):
        text = responses.get(node, "")
        if node == "repair" and counter is not None:
            counter["n"] += 1
            text = text + f"\n// iter {counter['n']}\n"
        log = {"node": node, "model": model, "provider": "fake", "run_id": run_id,
               "temperature": 0.7 if temperature is None else float(temperature),
               "tokens_in": 5, "tokens_out": 3, "latency_ms": 1, "rate_limit_retries": 0}
        return text, log
    for m in _NODE_MODS:
        monkeypatch.setattr(importlib.import_module(m), "llm_call", fake, raising=True)


def _install_icarus(monkeypatch, sim_results, compile_ok=True):
    import pipeline.nodes.evaluate as ev
    calls = {"n": 0}

    def _compile(drv, dut, timeout_s=30):
        return (compile_ok, "" if compile_ok else "syntax error near line 3", "/tmp/f.out")

    def _sim(path, timeout_s=30):
        i = min(calls["n"], len(sim_results) - 1)
        calls["n"] += 1
        return sim_results[i]

    monkeypatch.setattr(ev.icarus, "compile_tb", _compile)
    monkeypatch.setattr(ev.icarus, "simulate_tb", _sim)
    monkeypatch.setattr(ev.icarus, "eval2", lambda drv, muts, timeout_s=30: 1.0)
    monkeypatch.setattr(
        ev.icarus, "eval2_detailed",
        lambda drv, muts, timeout_s=30: (1.0, len(muts), len(muts), len(muts)),
    )
    monkeypatch.setattr(
        ev.icarus, "eval2_with_detail",
        lambda drv, muts, timeout_s=30: (1.0, len(muts), len(muts), len(muts), []),
    )
    monkeypatch.setattr("os.path.exists", lambda p: False)


def _state(run_id, **over):
    s = {
        "nl_description": "half adder", "module_name": "top_module", "golden_dut": "",
        "mutant_duts": ["m1"], "circuit_type": "CMB", "dut_rtl": "", "spec": {},
        "scenarios": [], "driver_rtl": "", "checker_py": "", "pyverilog_report": {},
        "error_report": [], "last_error_report": [], "scenario_results": [],
        "eval_dut_source": "generated", "repair_iter": 0, "max_repair_iter": 3,
        "oscillation_detected": False, "last_repair_signature": "", "feedback_source": "",
        "repair_history": [], "eval0_pass": False, "eval1_pass": False,
        "eval2_pass_rate": 0.0, "failure_stage": None, "final_status": "failed_compile",
        "run_id": run_id, "llm_calls": [],
    }
    s.update(over)
    return s


def test_hybrid_repairs_sim_failure_and_succeeds(monkeypatch):
    # Eval1 fails first, passes after one repair.
    _install_llm(monkeypatch, _CANNED, counter={"n": 0})
    _install_icarus(monkeypatch, [
        (False, "FAIL: zero\n"),
        (True, "PASS: zero\n"),
    ])
    final = build_graph(PipelineConfig(mode=AblationMode.HYBRID)).invoke(_state("loop_ok"))
    assert final["final_status"] == "success"
    assert final["repair_iter"] >= 1
    assert final["repair_iter"] <= final["max_repair_iter"]
    assert any(h["feedback_source"] == "simulation" for h in final["repair_history"])


def test_baseline_never_repairs(monkeypatch):
    _install_llm(monkeypatch, _CANNED)
    _install_icarus(monkeypatch, [(False, "FAIL: zero\n")])
    final = build_graph(PipelineConfig(mode=AblationMode.BASELINE)).invoke(_state("loop_base"))
    assert final["repair_iter"] == 0
    assert final["repair_history"] == []
    assert final["final_status"] == "failed_eval1"


def test_oscillation_terminates(monkeypatch):
    # repair returns the identical broken driver → oscillation on first attempt.
    responses = dict(_CANNED, repair=_DRIVER)  # same as gen_driver output
    _install_llm(monkeypatch, responses)       # no counter → identical each call
    _install_icarus(monkeypatch, [(False, "FAIL: zero\n")])
    final = build_graph(PipelineConfig(mode=AblationMode.HYBRID)).invoke(_state("loop_osc"))
    assert final["final_status"] == "oscillated"
    assert final["repair_iter"] <= final["max_repair_iter"]


def test_exhaustion_hits_budget(monkeypatch):
    # Distinct failing scenario each simulate call (→ changing signature) and a
    # unique repair driver each call (→ no identity oscillation) forces the loop
    # to run to the iteration budget.
    _install_llm(monkeypatch, _CANNED, counter={"n": 0})
    sim = [(False, f"FAIL: s{i}\n") for i in range(10)]
    _install_icarus(monkeypatch, sim)
    final = build_graph(PipelineConfig(mode=AblationMode.HYBRID)).invoke(_state("loop_exh"))
    assert final["final_status"] == "exhausted_iters"
    assert final["repair_iter"] == final["max_repair_iter"]


def test_compiler_only_repairs_compile_not_sim(monkeypatch):
    # Compile fails → COMPILER_ONLY should repair (and here then succeed on retry).
    _install_llm(monkeypatch, _CANNED, counter={"n": 0})
    import pipeline.nodes.evaluate as ev
    calls = {"n": 0}

    def _compile(drv, dut, timeout_s=30):
        calls["n"] += 1
        ok = calls["n"] > 1            # first compile fails, then succeeds
        return (ok, "" if ok else "syntax error", "/tmp/f.out")

    monkeypatch.setattr(ev.icarus, "compile_tb", _compile)
    monkeypatch.setattr(ev.icarus, "simulate_tb", lambda p, timeout_s=30: (True, "PASS: zero\n"))
    monkeypatch.setattr(ev.icarus, "eval2", lambda d, m, timeout_s=30: 1.0)
    monkeypatch.setattr(
        ev.icarus, "eval2_detailed",
        lambda d, m, timeout_s=30: (1.0, len(m), len(m), len(m)),
    )
    monkeypatch.setattr(
        ev.icarus, "eval2_with_detail",
        lambda d, m, timeout_s=30: (1.0, len(m), len(m), len(m), []),
    )
    monkeypatch.setattr("os.path.exists", lambda p: False)

    final = build_graph(PipelineConfig(mode=AblationMode.COMPILER_ONLY)).invoke(_state("loop_co"))
    assert final["repair_iter"] >= 1
    assert any(h["feedback_source"] == "compile" for h in final["repair_history"])
    assert final["final_status"] == "success"


# ── RETRY_ONLY control arm (Fix B) ────────────────────────────────────────────

def test_retry_only_regenerates_exactly_once(monkeypatch):
    """RETRY_ONLY draws one extra sample and then stops, regardless of outcome.

    This is the control for "an extra LLM generation": every repairing mode gets
    a second sample that BASELINE does not, so without this arm a gain over
    BASELINE cannot be attributed to the feedback.
    """
    _install_llm(monkeypatch, _CANNED, counter={"n": 0})
    # Simulation keeps failing — RETRY_ONLY must still stop after one resample.
    _install_icarus(monkeypatch, [(False, "FAIL: zero\n")])
    final = build_graph(PipelineConfig(mode=AblationMode.RETRY_ONLY)).invoke(
        _state("loop_retry")
    )
    assert final["repair_iter"] == 1
    assert len(final["repair_history"]) == 1
    assert final["repair_history"][0]["feedback_source"] == "none"


def test_retry_only_regenerates_even_when_static_report_is_clean(monkeypatch):
    """The resample is unconditional — it must not depend on the error report."""
    _install_llm(monkeypatch, _CANNED, counter={"n": 0})
    _install_icarus(monkeypatch, [(True, "PASS: zero\n")])
    final = build_graph(PipelineConfig(mode=AblationMode.RETRY_ONLY)).invoke(
        _state("loop_retry_clean", error_report=[])
    )
    assert final["repair_iter"] == 1
    assert final["final_status"] == "success"


def test_retry_only_never_uses_repair_node(monkeypatch):
    """RETRY_ONLY must never reach the repair node — that node consumes the error
    report, which would defeat the purpose of the control."""
    calls = {"repair": 0}
    responses = dict(_CANNED)

    def fake(*, node, model, prompt, run_id, max_tokens=4096, max_retries=3,
             temperature=None):
        if node == "repair":
            calls["repair"] += 1
        text = responses.get(node, "")
        if node in ("repair", "gen_driver"):
            text = text + f"\n// call {calls['repair']}\n"
        log = {"node": node, "model": model, "provider": "fake", "run_id": run_id,
               "temperature": 0.7, "tokens_in": 5, "tokens_out": 3,
               "latency_ms": 1, "rate_limit_retries": 0}
        return text, log

    for m in _NODE_MODS:
        monkeypatch.setattr(importlib.import_module(m), "llm_call", fake, raising=True)
    _install_icarus(monkeypatch, [(False, "FAIL: zero\n")])
    build_graph(PipelineConfig(mode=AblationMode.RETRY_ONLY)).invoke(
        _state("loop_retry_norepair")
    )
    assert calls["repair"] == 0
