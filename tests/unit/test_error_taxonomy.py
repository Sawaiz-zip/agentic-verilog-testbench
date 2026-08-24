"""Unit tests for error taxonomy data structures."""

import pytest
from pipeline.analysis.error_taxonomy import ErrorType, Severity, ErrorReportItem, PyverilogReport


def test_all_error_types_defined():
    expected = {
        "port_binding_mismatch",
        "undriven_input",
        "unobserved_output",
        "width_mismatch",
        "missing_fdisplay",
        "clock_never_toggled",
        "parse_failed",
    }
    assert {e.value for e in ErrorType} == expected


def test_every_declared_error_type_is_actually_emitted_somewhere():
    """A taxonomy entry that no check emits is a claim the implementation cannot
    back. WIDTH_MISMATCH sat unemitted for the whole project until the
    mixed-width fixtures made it testable; parse_failed is constructed via the
    PyverilogReport(parse_ok=False) path rather than as an ErrorReportItem."""
    import pathlib
    source = (pathlib.Path(__file__).parent.parent.parent
              / "pipeline" / "analysis" / "pyverilog_runner.py").read_text()
    exempt = {"parse_failed"}
    for member in ErrorType:
        if member.value in exempt:
            continue
        assert f"ErrorType.{member.name}" in source, (
            f"{member.name} is declared in the taxonomy but emitted nowhere"
        )


def test_severity_values():
    assert set(Severity) == {Severity.ERROR, Severity.WARNING, Severity.INFO}


def test_error_report_item_to_dict():
    item = ErrorReportItem(
        error_type=ErrorType.PORT_BINDING_MISMATCH,
        affected_signal="clk",
        line=14,
        suggested_fix="Connect clk to the clock port, not reset",
        severity=Severity.ERROR,
    )
    d = item.to_dict()
    assert d["error_type"] == "port_binding_mismatch"
    assert d["severity"] == "ERROR"
    assert d["line"] == 14


def test_pyverilog_report_is_clean_when_no_errors():
    report = PyverilogReport(parse_ok=True, parser_used="pyverilog")
    assert report.is_clean()
    assert report.all_errors() == []


def test_pyverilog_report_not_clean_with_errors():
    item = ErrorReportItem(
        error_type=ErrorType.UNDRIVEN_INPUT,
        affected_signal="a",
        line=None,
        suggested_fix="Drive input a in the testbench",
        severity=Severity.ERROR,
    )
    report = PyverilogReport(
        parse_ok=True,
        parser_used="pyverilog",
        dataflow_errors=[item],
    )
    assert not report.is_clean()
    assert len(report.all_errors()) == 1


def test_pyverilog_report_to_dict_structure():
    report = PyverilogReport(parse_ok=True, parser_used="verible")
    d = report.to_dict()
    assert "parse_ok" in d
    assert "parser_used" in d
    assert d["parser_used"] == "verible"
