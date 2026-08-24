"""
An exhausted balance must abort the sweep, not fail 100 runs one at a time.

The evaluation sweep is a single long run we only get to do once. If credit
runs out partway, every remaining (module, mode) pair would otherwise fail
individually — each with its own retries and exponential backoff — spending
hours to produce records that say nothing, and burying the runs that did
succeed.
"""

import pytest

from pipeline.eval.harness import _is_daily_rate_limit, _is_out_of_credits


class _Resp:
    def __init__(self, code):
        self.status_code = code


class _StatusError(Exception):
    def __init__(self, msg, code):
        super().__init__(msg)
        self.response = _Resp(code)


def test_http_402_is_recognised():
    assert _is_out_of_credits(_StatusError("Payment Required", 402)) is True


def test_status_code_attribute_is_recognised():
    exc = Exception("boom")
    exc.status_code = 402
    assert _is_out_of_credits(exc) is True


@pytest.mark.parametrize("msg", [
    "Insufficient credits to make this request",
    "You exceeded your current quota, please check your billing",
    "Error: payment required",
    "insufficient_quota",
])
def test_credit_messages_are_recognised(msg):
    assert _is_out_of_credits(Exception(msg)) is True


@pytest.mark.parametrize("msg", [
    "Rate limit reached for gpt-4o-mini",
    "Connection reset by peer",
    "model produced invalid JSON",
    "iverilog: command not found",
])
def test_ordinary_failures_are_not_mistaken_for_credit_exhaustion(msg):
    """A transient error must NOT abort the sweep — one bad run is isolated and
    the remaining runs still execute."""
    assert _is_out_of_credits(Exception(msg)) is False


def test_credit_and_daily_limit_are_distinguished():
    credit = _StatusError("Insufficient credits", 402)
    daily = Exception("Rate limit reached: tokens per day (TPD) exceeded")
    assert _is_out_of_credits(credit) and not _is_daily_rate_limit(credit)
    assert _is_daily_rate_limit(daily) and not _is_out_of_credits(daily)


# ── The sweep must actually stop ─────────────────────────────────────────────

def test_sweep_aborts_on_credit_exhaustion_and_keeps_completed_runs(tmp_path, monkeypatch):
    """Two runs succeed, the third hits a 402. The sweep must stop immediately
    rather than attempt the remaining pairs, and must still report what it
    already completed — a partial result is the whole value of aborting early.
    """
    from pipeline.config import AblationMode
    from pipeline.eval import harness

    monkeypatch.setattr(harness, "load_module", lambda *a, **k: {
        "task_id": "m", "module_name": "m", "nl_description": "x", "golden_dut": "",
    }, raising=False)

    calls = {"n": 0}

    def fake_invoke(graph, state):
        calls["n"] += 1
        if calls["n"] == 3:
            exc = Exception("Insufficient credits")
            exc.status_code = 402
            raise exc
        return {"final_status": "success"}

    modules = ["a", "b", "c", "d"]
    modes = [AblationMode.BASELINE, AblationMode.HYBRID]   # 8 pairs total

    out = harness.run_sweep(
        modules, modes, opt_in=True,
        results_dir=str(tmp_path), graph_invoke=fake_invoke,
    )

    assert out["aborted"] is True
    assert out["reason"] == "out_of_credits"
    # Stopped at the failing call: no further pairs were attempted.
    assert calls["n"] == 3, f"kept going after the 402 ({calls['n']} invocations)"
    assert out["ran"] == 2, out["ran"]


def test_sweep_survives_an_ordinary_run_failure(tmp_path, monkeypatch):
    """A transient failure must NOT abort — one bad run is isolated and the rest
    of the sweep still executes. Aborting on everything would be worse than not
    aborting at all."""
    from pipeline.config import AblationMode
    from pipeline.eval import harness

    monkeypatch.setattr(harness, "load_module", lambda *a, **k: {
        "task_id": "m", "module_name": "m", "nl_description": "x", "golden_dut": "",
    }, raising=False)

    calls = {"n": 0}

    def fake_invoke(graph, state):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("model produced invalid JSON")
        return {"final_status": "success"}

    out = harness.run_sweep(
        ["a", "b", "c"], [AblationMode.BASELINE],
        opt_in=True, results_dir=str(tmp_path), graph_invoke=fake_invoke,
    )
    assert out["aborted"] is False
    assert calls["n"] == 3, "a single bad run stopped the sweep"
