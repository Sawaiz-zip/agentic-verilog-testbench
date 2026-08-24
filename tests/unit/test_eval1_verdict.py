"""
Eval1 verdict must not be decided by a substring inside a scenario name.

Observed on the Day-2 smoke run: `fsm_sequence_detector` printed 8 PASS lines and
no FAIL line, yet Eval1 scored it a failure — because one scenario was named
`immediate_mismatch` and the verdict searched the whole output for the bare
substring "mismatch". A fully correct testbench was recorded as failing, which
would have propagated straight into the ablation table.
"""

from pipeline.eval.icarus import _has_mismatch_report

_EIGHT_PASSES = (
    "PASS: detect_sequence_1011\n"
    "PASS: overlapping_detection_1\n"
    "PASS: reset_condition\n"
    "PASS: immediate_mismatch\n"
    "PASS: no_detection_sequence\n"
    "PASS: single_bit_detection\n"
    "PASS: partial_sequence_detection\n"
    "PASS: transitions_without_full_sequence\n"
    "/tmp/tb_x.v:188: $finish called at 646 (1s)"
)


def test_scenario_named_mismatch_does_not_fail_a_passing_run():
    assert _has_mismatch_report(_EIGHT_PASSES) is False


def test_real_mismatch_report_is_detected():
    assert _has_mismatch_report("Mismatches: 3 in 100 samples") is True


def test_hint_style_mismatch_report_is_detected():
    assert _has_mismatch_report("Hint: Output q has 12 mismatches") is True


def test_zero_mismatch_report_is_a_success_not_a_failure():
    """A VerilogEval reference testbench prints its mismatch count on success too;
    'Mismatches: 0' reports that nothing went wrong."""
    assert _has_mismatch_report("Mismatches: 0 in 100 samples out of 100") is False
    assert _has_mismatch_report("0 mismatches") is False


def test_case_insensitive_and_indifferent_to_surrounding_lines():
    out = "PASS: setup\nMISMATCH detected on signal q\nPASS: teardown"
    assert _has_mismatch_report(out) is True


def test_simulate_verdict_end_to_end(monkeypatch, tmp_path):
    """The full verdict path, not just the helper: a run with only PASS lines and a
    mismatch-named scenario must be reported as passing."""
    import subprocess

    import pipeline.eval.icarus as icarus

    binary = tmp_path / "fake.out"
    binary.write_text("")

    class _R:
        stdout = _EIGHT_PASSES
        stderr = ""
        returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _R())
    passed, out = icarus.simulate_tb(str(binary))
    assert passed is True
    assert "immediate_mismatch" in out
