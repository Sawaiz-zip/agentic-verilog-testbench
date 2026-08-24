"""
Pyverilog-based static analysis of generated testbench vs golden DUT.
Checks: port bindings, undriven inputs, unobserved outputs, sensitivity lists,
$fdisplay presence.
RQ1 + RQ2.

Smoke-test findings (Phase 0, 2026-06-23):
  - AST parse works on all tested modules.
  - VerilogEval .sv files use Verilog-2001 port style: ports are wrapped in
    `vast.Ioport` nodes whose `.first` child is the actual Input/Output.
    Always check `isinstance(item, vast.Ioport)` before accessing `.name`.
  - Dataflow raises `pyverilog.utils.verror.FormatError: Illegal sensitivity
    list` on modules with async reset (`always @(posedge clk or posedge ar)`).
    Mitigation: catch FormatError and fall back to AST-only for those modules.
  - The LALR-table "183 shift/reduce conflicts" warning is normal; harmless.
"""

import io
import os
import sys
import tempfile

import pyverilog.vparser.ast as vast
import pyverilog.vparser.parser as vparser

from pipeline.analysis.error_taxonomy import (
    ErrorReportItem,
    ErrorType,
    PyverilogReport,
    Severity,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_ports(module_def) -> list[tuple[str, str]]:
    """Return [(direction, name), ...] handling both Port and Ioport styles."""
    ports = []
    for item in module_def.portlist.ports:
        if isinstance(item, vast.Ioport):
            decl = item.first
            ports.append((decl.__class__.__name__, decl.name))
        elif hasattr(item, "name"):
            ports.append(("unknown", item.name))
    return ports


def _find_module_defs(ast) -> dict[str, object]:
    """Return {module_name: ModuleDef} for all modules in parsed AST."""
    return {
        m.name: m
        for m in (ast.description.definitions or [])
        if isinstance(m, vast.ModuleDef)
    }


def _find_dut_instances(tb_module, dut_module_name: str) -> list:
    """Return all Instance objects inside tb_module that instantiate dut_module_name."""
    instances = []
    for item in (tb_module.items or []):
        if isinstance(item, vast.InstanceList) and item.module == dut_module_name:
            instances.extend(item.instances)
    return instances


def _has_posedge(verilog_text: str) -> bool:
    return "posedge" in verilog_text


def _has_display_for_signal(tb_verilog: str, signal_name: str) -> bool:
    """Heuristic: does the TB text contain a display/fdisplay referencing signal_name?"""
    lower = tb_verilog.lower()
    for kw in ("$fdisplay", "$display", "$monitor", "$write"):
        idx = 0
        while True:
            pos = lower.find(kw, idx)
            if pos == -1:
                break
            end = tb_verilog.find(";", pos)
            fragment = tb_verilog[pos:end] if end != -1 else tb_verilog[pos:]
            if signal_name in fragment:
                return True
            idx = pos + 1
    return False


def _signal_is_driven(tb_verilog: str, signal_name: str) -> bool:
    """
    Heuristic: signal appears on the left side of an assignment in the TB.
    Covers `signal = ...`, `signal <= ...`, and reg initial values.
    """
    import re
    pattern = rf'\b{re.escape(signal_name)}\s*(<=|=)'
    return bool(re.search(pattern, tb_verilog))


def _output_is_observed(tb_verilog: str, signal_name: str) -> bool:
    """
    Heuristic: does the TB check or print this output signal?
    Covers comparisons (===, !==, ==, !=), if-conditions, and display calls.
    """
    import re
    # Comparison: signal === ..., signal !== ..., signal == ..., signal != ...
    if re.search(rf'\b{re.escape(signal_name)}\s*(===|!==|==|!=)', tb_verilog):
        return True
    # Reverse comparison: ... === signal
    if re.search(rf'(===|!==|==|!=)\s*{re.escape(signal_name)}\b', tb_verilog):
        return True
    # Appears inside an if(...) condition
    if re.search(rf'if\s*\([^)]*\b{re.escape(signal_name)}\b', tb_verilog):
        return True
    # Display/fdisplay/monitor call includes this signal
    if _has_display_for_signal(tb_verilog, signal_name):
        return True
    return False


# ── Port-binding check ────────────────────────────────────────────────────────

def _check_port_bindings(
    instances: list, dut_ports: list[tuple[str, str]], module_name: str
) -> list[ErrorReportItem]:
    if not instances:
        return [
            ErrorReportItem(
                error_type=ErrorType.PORT_BINDING_MISMATCH,
                affected_signal="(none)",
                line=None,
                suggested_fix=(
                    f"Testbench does not instantiate module '{module_name}'. "
                    "Add an instance: "
                    f"{module_name} dut(<port connections>);"
                ),
                severity=Severity.ERROR,
            )
        ]

    dut_port_names = {name for _, name in dut_ports}
    errors: list[ErrorReportItem] = []

    for inst in instances:
        portargs = inst.portlist or []
        # Only check named connections (positional connections cannot be checked by name)
        named = [(pa.portname, pa) for pa in portargs if pa.portname is not None]
        connected_names = {portname for portname, _ in named}

        # Unknown port names (exist in TB instance but not in DUT)
        for portname, pa in named:
            if portname not in dut_port_names:
                lineno = getattr(pa, "lineno", None)
                errors.append(
                    ErrorReportItem(
                        error_type=ErrorType.PORT_BINDING_MISMATCH,
                        affected_signal=portname,
                        line=lineno,
                        suggested_fix=(
                            f"Port '{portname}' does not exist in {module_name}. "
                            f"Valid ports: {sorted(dut_port_names)}"
                        ),
                        severity=Severity.ERROR,
                    )
                )

        # Missing ports (in DUT but not in TB instance)
        for _, port_name in dut_ports:
            if port_name not in connected_names:
                errors.append(
                    ErrorReportItem(
                        error_type=ErrorType.PORT_BINDING_MISMATCH,
                        affected_signal=port_name,
                        line=None,
                        suggested_fix=(
                            f"Port '{port_name}' of {module_name} is not connected "
                            "in the testbench instance. Add '.{port_name}(<signal>)'."
                        ),
                        severity=Severity.ERROR,
                    )
                )

    return errors


# ── Undriven / unobserved checks ──────────────────────────────────────────────

def _check_driven_observed(
    instances: list,
    dut_ports: list[tuple[str, str]],
    tb_verilog: str,
) -> list[ErrorReportItem]:
    """
    Heuristic checks using text search on the TB source.
    For each DUT input: find connected TB signal, check if it's ever assigned.
    For each DUT output: find connected TB signal, check if it's ever read in a
    display or comparison.
    """
    if not instances:
        return []

    errors: list[ErrorReportItem] = []
    # Build map: dut_port_name → connected_tb_signal_name (from first instance)
    inst = instances[0]
    port_to_signal: dict[str, str] = {}
    for pa in (inst.portlist or []):
        if pa.portname and pa.argname is not None:
            # argname is an AST node — get its name string
            if hasattr(pa.argname, "name"):
                port_to_signal[pa.portname] = pa.argname.name
            elif hasattr(pa.argname, "var"):
                port_to_signal[pa.portname] = str(pa.argname.var)

    input_types = {"Input", "Inout"}
    output_types = {"Output", "Inout"}

    for direction, port_name in dut_ports:
        connected_signal = port_to_signal.get(port_name, port_name)

        if direction in input_types:
            if not _signal_is_driven(tb_verilog, connected_signal):
                errors.append(
                    ErrorReportItem(
                        error_type=ErrorType.UNDRIVEN_INPUT,
                        affected_signal=port_name,
                        line=None,
                        suggested_fix=(
                            f"DUT input '{port_name}' (connected to TB signal "
                            f"'{connected_signal}') is never assigned a value. "
                            "Add assignments in initial/always block."
                        ),
                        severity=Severity.WARNING,
                    )
                )

        if direction in output_types:
            if not _output_is_observed(tb_verilog, connected_signal):
                errors.append(
                    ErrorReportItem(
                        error_type=ErrorType.UNOBSERVED_OUTPUT,
                        affected_signal=port_name,
                        line=None,
                        suggested_fix=(
                            f"DUT output '{port_name}' (connected to TB signal "
                            f"'{connected_signal}') is never checked or displayed. "
                            "Add a comparison or $display statement."
                        ),
                        severity=Severity.WARNING,
                    )
                )

    return errors


# ── Sensitivity list check (SEQ) ─────────────────────────────────────────────

def _check_sensitivity_lists(tb_module) -> list[ErrorReportItem]:
    """
    For sequential circuits: verify TB always-blocks use posedge/negedge clock.
    If always-blocks exist but none have an edge trigger → SENSITIVITY_LIST_ERROR.
    Only called when the DUT contains 'posedge' (is_seq=True).
    """
    always_blocks = [
        item for item in (tb_module.items or [])
        if isinstance(item, vast.Always)
    ]
    if not always_blocks:
        return []

    def _has_edge_trigger(always_block) -> bool:
        sens_list = always_block.sens_list
        if sens_list is None:
            return False
        for sens in (sens_list.list or []):
            if getattr(sens, "type", None) in ("posedge", "negedge"):
                return True
        return False

    if any(_has_edge_trigger(ab) for ab in always_blocks):
        return []

    # All always-blocks exist but none are clock-triggered
    first_line = getattr(always_blocks[0], "lineno", None)
    return [
        ErrorReportItem(
            error_type=ErrorType.SENSITIVITY_LIST_ERROR,
            affected_signal="clk",
            line=first_line,
            suggested_fix=(
                "Testbench has always-blocks but none use posedge/negedge clock "
                "sensitivity. For a sequential DUT add: always @(posedge clk) begin "
                "... end"
            ),
            severity=Severity.WARNING,
        )
    ]


# ── $fdisplay check (SEQ) ─────────────────────────────────────────────────────

def _check_fdisplay(
    instances: list,
    dut_ports: list[tuple[str, str]],
    tb_verilog: str,
) -> list[ErrorReportItem]:
    """Check that every DUT output has a $fdisplay/$display/$monitor in the TB."""
    if not instances:
        return []

    inst = instances[0]
    port_to_signal: dict[str, str] = {}
    for pa in (inst.portlist or []):
        if pa.portname and pa.argname is not None:
            if hasattr(pa.argname, "name"):
                port_to_signal[pa.portname] = pa.argname.name

    errors: list[ErrorReportItem] = []
    for direction, port_name in dut_ports:
        if direction not in ("Output", "Inout"):
            continue
        connected = port_to_signal.get(port_name, port_name)
        # Observation criterion must match the deterministic standardiser's
        # `_is_observed` (standardiser/fdisplay_inserter.py). Previously this
        # check demanded the signal appear *inside* a $display argument list,
        # while the standardiser accepted an `if (q === ...)` self-check — so a
        # testbench that correctly checks its outputs was flagged by one
        # component and left alone by the other. That disagreement produced a
        # false positive on every self-checking SEQ testbench.
        if not _output_is_observed(tb_verilog, connected):
            errors.append(
                ErrorReportItem(
                    error_type=ErrorType.MISSING_FDISPLAY,
                    affected_signal=port_name,
                    line=None,
                    suggested_fix=(
                        f"DUT output '{port_name}' (TB signal '{connected}') is "
                        "never printed or compared. For a sequential circuit the "
                        "output must be observable every cycle — add a $monitor "
                        "or a per-cycle comparison."
                    ),
                    severity=Severity.WARNING,
                )
            )
    return errors


# ── Main entry point ──────────────────────────────────────────────────────────

def run(
    tb_verilog: str,
    dut_verilog: str,
    module_name: str = "",
) -> PyverilogReport:
    """
    Parse TB + DUT together with Pyverilog and return a structured report.
    Raises nothing — on Pyverilog parse failure returns PyverilogReport(parse_ok=False).
    Caller (pyverilog_analysis_node) may then try verible_runner as fallback.
    """
    tb_fd = dut_fd = -1
    tb_path = dut_path = ""
    try:
        tb_fd, tb_path = tempfile.mkstemp(suffix=".v", prefix="tb_")
        dut_fd, dut_path = tempfile.mkstemp(suffix=".v", prefix="dut_")
        os.close(tb_fd); tb_fd = -1
        os.close(dut_fd); dut_fd = -1

        # Ensure a trailing newline. Pyverilog concatenates the two files; without
        # it, a TB ending in "endmodule" (no newline) glues onto the DUT's
        # "module ..." as one token ("endmodulemodule"), which breaks the parse
        # at the DUT — silently disabling all static analysis.
        with open(tb_path, "w") as f:
            f.write(tb_verilog if tb_verilog.endswith("\n") else tb_verilog + "\n")
        with open(dut_path, "w") as f:
            f.write(dut_verilog if dut_verilog.endswith("\n") else dut_verilog + "\n")

        # Suppress pyverilog's verbose LALR warnings
        _null = open(os.devnull, "w")
        old_stderr = sys.stderr
        sys.stderr = _null
        try:
            ast, _ = vparser.parse(
                [tb_path, dut_path],
                preprocess_include=[],
                preprocess_define=[],
            )
        finally:
            sys.stderr = old_stderr
            _null.close()

    except Exception as exc:
        return PyverilogReport(
            parse_ok=False,
            parser_used="pyverilog",
            raw_warnings=[f"Pyverilog parse error: {exc}"],
        )
    finally:
        for fd in (tb_fd, dut_fd):
            if fd != -1:
                try:
                    os.close(fd)
                except OSError:
                    pass
        for path in (tb_path, dut_path):
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass

    # ── Resolve module names ──────────────────────────────────────────────────
    module_defs = _find_module_defs(ast)
    if not module_name or module_name not in module_defs:
        # Guess: DUT is the module defined in dut_verilog.
        # We re-parse just the DUT to find its name.
        try:
            dut_fd2, dut_path2 = tempfile.mkstemp(suffix=".v", prefix="dut2_")
            os.close(dut_fd2)
            with open(dut_path2, "w") as f:
                f.write(dut_verilog)
            _null2 = open(os.devnull, "w")
            old_stderr2 = sys.stderr
            sys.stderr = _null2
            try:
                dut_ast, _ = vparser.parse([dut_path2])
            finally:
                sys.stderr = old_stderr2
                _null2.close()
            os.unlink(dut_path2)
            dut_mods = _find_module_defs(dut_ast)
            if dut_mods:
                module_name = next(iter(dut_mods))
        except Exception:
            pass

    if module_name not in module_defs:
        return PyverilogReport(
            parse_ok=True,
            parser_used="pyverilog",
            raw_warnings=[
                f"Could not identify DUT module '{module_name}' in parsed AST. "
                f"Found modules: {list(module_defs.keys())}"
            ],
        )

    dut_module = module_defs[module_name]
    # TB is the module that is NOT the DUT
    tb_candidates = [m for name, m in module_defs.items() if name != module_name]
    if not tb_candidates:
        return PyverilogReport(
            parse_ok=True,
            parser_used="pyverilog",
            raw_warnings=["Only one module found in combined AST — cannot separate TB from DUT."],
        )
    tb_module = tb_candidates[0]

    dut_ports = _extract_ports(dut_module)
    instances = _find_dut_instances(tb_module, module_name)
    is_seq = _has_posedge(dut_verilog)

    # ── Run checks ────────────────────────────────────────────────────────────
    port_errors = _check_port_bindings(instances, dut_ports, module_name)

    # Only run undriven/unobserved if port bindings look okay (avoid noise)
    if not port_errors:
        dataflow_errors = _check_driven_observed(instances, dut_ports, tb_verilog)
    else:
        dataflow_errors = []

    sensitivity_errors: list[ErrorReportItem] = []
    fdisplay_missing: list[ErrorReportItem] = []
    if is_seq:
        sensitivity_errors = _check_sensitivity_lists(tb_module)
        fdisplay_missing = _check_fdisplay(instances, dut_ports, tb_verilog)
        # MISSING_FDISPLAY and UNOBSERVED_OUTPUT now share an observation
        # criterion, so an unobserved SEQ output would otherwise be reported
        # twice and double-counted in the taxonomy. Keep the SEQ-specific class.
        _seq_reported = {e.affected_signal for e in fdisplay_missing}
        dataflow_errors = [
            e for e in dataflow_errors
            if not (
                e.error_type == ErrorType.UNOBSERVED_OUTPUT
                and e.affected_signal in _seq_reported
            )
        ]

    return PyverilogReport(
        parse_ok=True,
        parser_used="pyverilog",
        port_errors=port_errors,
        sensitivity_errors=sensitivity_errors,
        dataflow_errors=dataflow_errors,
        fdisplay_missing=fdisplay_missing,
        raw_warnings=[],
    )
