"""T025 — evaluate_node result JSON: new fields + eval DUT selection."""

import json

from pipeline.nodes.evaluate import evaluate_node


def _state(**over):
    s = {
        "run_id": "evaltest",
        "module_name": "top_module",
        "circuit_type": "CMB",
        "nl_description": "a half adder circuit",
        "dut_rtl": "module top_module(); endmodule",
        "golden_dut": "",
        "driver_rtl": "module testbench; endmodule",
        "mutant_duts": ["m1"],   # skip mutant generation (no LLM)
        "repair_iter": 0,
        "llm_calls": [
            {"node": "gen_dut", "tokens_in": 20, "tokens_out": 8, "temperature": 0.7},
        ],
    }
    s.update(over)
    return s


def _read_result(run_id):
    import pathlib
    root = pathlib.Path(__file__).parent.parent.parent
    return json.loads((root / "results" / f"{run_id}.json").read_text())


def test_result_has_new_fields_generated_dut(mock_icarus):
    evaluate_node(_state(run_id="evt_gen"))
    r = _read_result("evt_gen")
    assert r["nl_description"] == "a half adder circuit"
    assert r["eval_dut_source"] == "generated"
    assert r["scenario_results"] == [
        {"name": "zero", "passed": True},
        {"name": "both", "passed": True},
    ]
    assert r["scenarios_passed"] == 2
    assert r["scenarios_total"] == 2
    assert r["tokens_in_total"] == 20
    assert r["tokens_out_total"] == 8
    assert r["dut_rtl"] == "module top_module(); endmodule"


def test_eval_dut_source_golden_when_present(mock_icarus):
    evaluate_node(_state(run_id="evt_gold", golden_dut="module golden(); endmodule"))
    r = _read_result("evt_gold")
    assert r["eval_dut_source"] == "golden"


def test_best_so_far_reports_earlier_better_tb(mock_icarus_flaky):
    """Issue A: a later repair iteration that regresses must NOT worsen the
    reported result — the best-scoring testbench is reported instead."""
    # Iter 1: GOOD testbench passes Eval1 (2/2). Iter 2: BAD testbench regresses.
    mock_icarus_flaky.sim_results = [
        (True, "PASS: zero\nPASS: both\n"),
        (False, "PASS: zero\nFAIL: both\n"),
    ]
    first = evaluate_node(_state(run_id="bestsofar", driver_rtl="GOOD_TB"))
    # Feed iter-1's best forward; iter 2 is worse and exhausts the budget.
    evaluate_node(_state(
        run_id="bestsofar", driver_rtl="BAD_TB",
        best_snapshot=first["best_snapshot"], repair_iter=3, max_repair_iter=3,
    ))
    r = _read_result("bestsofar")
    # Reported quality reflects the GOOD (best) TB, not the regressed last one…
    assert r["eval1_pass"] is True
    assert r["scenarios_passed"] == 2
    assert r["driver_rtl"] == "GOOD_TB"
    # …while the terminal status still records that the loop exhausted its budget.
    assert r["final_status"] == "exhausted_iters"


def test_best_so_far_updates_on_improvement(mock_icarus_flaky):
    """The opposite direction: a later iteration that improves IS adopted."""
    mock_icarus_flaky.sim_results = [
        (False, "PASS: zero\nFAIL: both\n"),   # iter 1: 1/2, fails
        (True, "PASS: zero\nPASS: both\n"),    # iter 2: 2/2, passes
    ]
    first = evaluate_node(_state(run_id="improve", driver_rtl="BAD_TB"))
    second = evaluate_node(_state(
        run_id="improve", driver_rtl="GOOD_TB", best_snapshot=first["best_snapshot"],
    ))
    r = _read_result("improve")
    assert r["eval1_pass"] is True
    assert r["driver_rtl"] == "GOOD_TB"
    assert second["best_snapshot"]["driver_rtl"] == "GOOD_TB"
