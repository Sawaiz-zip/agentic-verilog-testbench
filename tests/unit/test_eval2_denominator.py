"""
Fix D — Eval2 must score against *valid* mutants only.

A mutant that does not compile is a bad mutation, not a bug the testbench
failed to catch. Counting it in the denominator silently capped the score:
one broken mutant out of five pinned the maximum at 0.8, which is
indistinguishable from a genuinely imperfect testbench in the results table.
"""

import pipeline.eval.icarus as icarus


def _install(monkeypatch, compile_results, sim_results):
    """compile_results/sim_results are consumed one per mutant, in order."""
    c = {"n": 0}
    s = {"n": 0}

    def _compile(drv, dut, timeout_s=30):
        ok = compile_results[c["n"]]
        c["n"] += 1
        return (ok, "" if ok else "syntax error", "/tmp/f.out")

    def _sim(path, timeout_s=30):
        r = sim_results[s["n"]]
        s["n"] += 1
        return (r, "")

    monkeypatch.setattr(icarus, "compile_tb", _compile)
    monkeypatch.setattr(icarus, "simulate_tb", _sim)
    monkeypatch.setattr("os.path.exists", lambda p: False)


def test_invalid_mutants_are_excluded_from_the_denominator(monkeypatch):
    # 5 mutants, 1 fails to compile; the testbench catches all 4 valid ones.
    _install(monkeypatch, [True, True, False, True, True], [False, False, False, False])
    rate, caught, valid, total = icarus.eval2_detailed("tb", ["m"] * 5)
    assert (caught, valid, total) == (4, 4, 5)
    assert rate == 1.0          # was 0.8 before the fix


def test_uncaught_valid_mutants_still_lower_the_score(monkeypatch):
    # 4 valid mutants, testbench catches 2 → 0.5. Validity must not mask misses.
    _install(monkeypatch, [True, True, True, True], [False, True, False, True])
    rate, caught, valid, total = icarus.eval2_detailed("tb", ["m"] * 4)
    assert (caught, valid, total) == (2, 4, 4)
    assert rate == 0.5


def test_all_mutants_invalid_scores_zero_not_a_crash(monkeypatch):
    _install(monkeypatch, [False, False], [])
    rate, caught, valid, total = icarus.eval2_detailed("tb", ["m"] * 2)
    assert (rate, caught, valid, total) == (0.0, 0, 0, 2)


def test_no_mutants_scores_zero(monkeypatch):
    assert icarus.eval2_detailed("tb", []) == (0.0, 0, 0, 0)


def test_eval2_wrapper_matches_detailed_rate(monkeypatch):
    _install(monkeypatch, [True, True, False], [False, True])
    assert icarus.eval2("tb", ["m"] * 3) == 0.5


# ── Per-mutant auditability ──────────────────────────────────────────────────

def test_per_mutant_detail_identifies_which_mutant_escaped(monkeypatch):
    """Aggregate counts cannot say *which* mutant survived. A 189/190 score is
    indistinguishable from mutants being too easy unless the escapee can be
    identified after the fact — and regenerating them would produce different
    ones, so it has to be recorded at the time."""
    _install(monkeypatch, [True, True, True], [False, True, False])
    rate, caught, valid, total, detail = icarus.eval2_with_detail("tb", ["m"] * 3)
    assert (caught, valid, total) == (2, 3, 3)
    escaped = [d["index"] for d in detail if d["compiled"] and not d["caught"]]
    assert escaped == [1], detail


def test_non_compiling_mutant_is_recorded_as_such(monkeypatch):
    _install(monkeypatch, [True, False], [False])
    _rate, _c, _v, _t, detail = icarus.eval2_with_detail("tb", ["m"] * 2)
    assert detail[1]["compiled"] is False
    assert detail[1]["caught"] is None      # never ran, so neither caught nor missed
    assert detail[1]["note"]


def test_detail_has_one_entry_per_mutant(monkeypatch):
    _install(monkeypatch, [True, True, False, True], [False, False, False])
    _r, _c, _v, _t, detail = icarus.eval2_with_detail("tb", ["m"] * 4)
    assert len(detail) == 4
    assert [d["index"] for d in detail] == [0, 1, 2, 3]
