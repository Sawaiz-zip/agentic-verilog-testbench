"""
Error type constants and data structures for Pyverilog analysis output.
RQ1: defines the testbench error taxonomy.
"""

from dataclasses import dataclass, field
from enum import Enum


class ErrorType(str, Enum):
    PORT_BINDING_MISMATCH = "port_binding_mismatch"
    UNDRIVEN_INPUT = "undriven_input"
    UNOBSERVED_OUTPUT = "unobserved_output"
    WIDTH_MISMATCH = "width_mismatch"
    MISSING_FDISPLAY = "missing_fdisplay"
    CLOCK_NEVER_TOGGLED = "clock_never_toggled"
    PARSE_FAILED = "parse_failed"


class Severity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class ErrorReportItem:
    error_type: ErrorType
    affected_signal: str
    line: int | None
    suggested_fix: str
    severity: Severity

    def to_dict(self) -> dict:
        return {
            "error_type": self.error_type.value,
            "affected_signal": self.affected_signal,
            "line": self.line,
            "suggested_fix": self.suggested_fix,
            "severity": self.severity.value,
        }


@dataclass
class PyverilogReport:
    parse_ok: bool
    parser_used: str           # "pyverilog" or "verible"
    port_errors: list[ErrorReportItem] = field(default_factory=list)
    # Clock-behaviour findings. Named `sensitivity_errors` until the
    # sensitivity-list check was dropped for zero measured recall; it now
    # carries clock-toggle findings only.
    clock_errors: list[ErrorReportItem] = field(default_factory=list)
    dataflow_errors: list[ErrorReportItem] = field(default_factory=list)
    fdisplay_missing: list[ErrorReportItem] = field(default_factory=list)
    raw_warnings: list[str] = field(default_factory=list)

    def all_errors(self) -> list[ErrorReportItem]:
        return (
            self.port_errors
            + self.clock_errors
            + self.dataflow_errors
            + self.fdisplay_missing
        )

    def is_clean(self) -> bool:
        return len(self.all_errors()) == 0

    def to_dict(self) -> dict:
        return {
            "parse_ok": self.parse_ok,
            "parser_used": self.parser_used,
            "port_errors": [e.to_dict() for e in self.port_errors],
            "clock_errors": [e.to_dict() for e in self.clock_errors],
            "dataflow_errors": [e.to_dict() for e in self.dataflow_errors],
            "fdisplay_missing": [e.to_dict() for e in self.fdisplay_missing],
            "raw_warnings": self.raw_warnings,
        }
