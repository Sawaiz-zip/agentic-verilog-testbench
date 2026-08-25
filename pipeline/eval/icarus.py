"""
Icarus Verilog wrapper.
Eval0: does the testbench compile?
Eval1: does it pass against the golden DUT?
Eval2: does it catch bugs in mutant DUTs?
"""

import os
import re
import subprocess
import tempfile


def compile_tb(
    driver_rtl: str, dut_verilog: str, timeout_s: int = 30
) -> tuple[bool, str, str]:
    """
    Eval0: compile TB + DUT with iverilog.
    Returns (success, compiler_output, compiled_binary_path).
    compiled_binary_path is "" on failure.
    Caller is responsible for deleting compiled_binary_path when done.
    """
    tb_fd, tb_path = tempfile.mkstemp(suffix=".v", prefix="tb_")
    dut_fd, dut_path = tempfile.mkstemp(suffix=".v", prefix="dut_")
    out_fd, out_path = tempfile.mkstemp(suffix=".out", prefix="sim_")
    os.close(tb_fd)
    os.close(dut_fd)
    os.close(out_fd)

    try:
        with open(tb_path, "w") as f:
            f.write(driver_rtl)
        with open(dut_path, "w") as f:
            f.write(dut_verilog)

        result = subprocess.run(
            ["iverilog", "-g2012", "-o", out_path, tb_path, dut_path],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        output = (result.stdout + result.stderr).strip()
        success = result.returncode == 0
        if not success and os.path.exists(out_path):
            os.unlink(out_path)
            out_path = ""
        return success, output, out_path if success else ""

    except subprocess.TimeoutExpired:
        return False, "iverilog timed out", ""
    finally:
        for p in [tb_path, dut_path]:
            try:
                os.unlink(p)
            except OSError:
                pass


# A VerilogEval-style reference testbench reports failures as "Mismatches: N in M
# samples". Searching the whole output for the bare substring "mismatch" is unsafe on
# two counts, both observed: a *scenario name* can contain it (a run with 8/8 PASS and
# a scenario called "immediate_mismatch" was scored as a failure), and a zero-mismatch
# line is a report of success, not of failure.
_ZERO_MISMATCH_RE = re.compile(r"\b0\s+mismatch|mismatches\s*:?\s*0\b", re.IGNORECASE)
_MISMATCH_RE = re.compile(r"\bmismatch(es)?\b", re.IGNORECASE)


def _has_mismatch_report(output: str) -> bool:
    """True only for a line that actually reports a non-zero mismatch count."""
    for line in output.splitlines():
        stripped = line.strip()
        # A passing scenario line is a verdict, not a report — its name is free text.
        if stripped.upper().startswith("PASS:"):
            continue
        if _MISMATCH_RE.search(stripped) and not _ZERO_MISMATCH_RE.search(stripped):
            return True
    return False


def simulate_tb(compiled_path: str, timeout_s: int = 30) -> tuple[bool, str]:
    """
    Eval1: run compiled simulation with vvp.
    Returns (passed, simulation_output).
    passed=True if the output contains no FAIL markers and vvp exits normally.
    """
    if not compiled_path or not os.path.exists(compiled_path):
        return False, "compiled binary not found"

    try:
        result = subprocess.run(
            ["vvp", compiled_path],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        output = (result.stdout + result.stderr).strip()
        # Our prompt instructs the TB to print exactly "FAIL: <name>" on failure.
        # Match that precisely to avoid catching words like "failed" in debug prints.
        has_fail_marker = bool(re.search(r'\bFAIL\s*:', output))
        has_mismatch    = _has_mismatch_report(output)
        has_error_crash = result.returncode not in (0, 1)
        failed = has_fail_marker or has_mismatch or has_error_crash
        return not failed, output

    except subprocess.TimeoutExpired:
        return False, f"vvp timed out after {timeout_s}s"


def eval2_detailed(
    driver_rtl: str, mutant_duts: list[str], timeout_s: int = 30
) -> tuple[float, int, int, int]:
    """
    Eval2: run TB against each mutant DUT.
    Returns (pass_rate, caught, valid, total).

    A mutant that does not compile is an INVALID mutant — the LLM produced a
    broken mutation, not a bug the testbench failed to catch. Such mutants are
    excluded from BOTH numerator and denominator. (They were previously skipped
    in the numerator but still counted in the denominator, which silently capped
    the score: one bad mutant out of five pinned the maximum at 0.8.)
    """
    rate, caught, valid, total, _detail = eval2_with_detail(
        driver_rtl, mutant_duts, timeout_s
    )
    return rate, caught, valid, total


def eval2_with_detail(
    driver_rtl: str, mutant_duts: list[str], timeout_s: int = 30
) -> tuple[float, int, int, int, list[dict]]:
    """As eval2_detailed, plus a per-mutant record.

    Aggregate counts cannot say *which* mutant escaped, so a near-ceiling score
    (189/190 in one sweep) is indistinguishable from mutants being too easy.
    The per-mutant record makes that auditable after the fact, without re-running
    the sweep.
    """
    total = len(mutant_duts)
    if total == 0:
        return 0.0, 0, 0, 0, []

    caught = 0
    valid = 0
    detail: list[dict] = []
    for i, mutant_verilog in enumerate(mutant_duts):
        success, compiler_out, compiled_path = compile_tb(
            driver_rtl, mutant_verilog, timeout_s=timeout_s
        )
        if not success:
            detail.append({"index": i, "compiled": False, "caught": None,
                           "note": compiler_out.strip().splitlines()[0][:160]
                                   if compiler_out.strip() else "did not compile"})
            continue
        valid += 1
        try:
            passed, _sim_out = simulate_tb(compiled_path, timeout_s=timeout_s)
            was_caught = not passed
            if was_caught:
                # TB detected the bug in this mutant
                caught += 1
            detail.append({"index": i, "compiled": True, "caught": was_caught})
        finally:
            if compiled_path and os.path.exists(compiled_path):
                try:
                    os.unlink(compiled_path)
                except OSError:
                    pass

    rate = (caught / valid) if valid else 0.0
    return rate, caught, valid, total, detail


def eval2(driver_rtl: str, mutant_duts: list[str], timeout_s: int = 30) -> float:
    """Fraction of *valid* mutants the testbench detects. See eval2_detailed."""
    rate, _caught, _valid, _total = eval2_detailed(driver_rtl, mutant_duts, timeout_s)
    return rate
