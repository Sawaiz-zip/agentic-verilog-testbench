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
import re
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


def _const_int(node) -> int | None:
    """Integer value of a constant AST node, or None if it is not a plain constant.

    Widths given by a parameter or an expression are deliberately not resolved —
    a width we cannot evaluate must produce no finding rather than a guess.
    """
    if node is None:
        return None
    value = getattr(node, "value", None)
    if value is None:
        return None
    try:
        text = str(value).strip()
        # Sized literals such as 4'd7 — take the part after the base.
        if "'" in text:
            text = re.sub(r"^\d*'[sSbBoOdDhH]*", "", text)
            return int(text, 0)
        return int(text, 0)
    except (TypeError, ValueError):
        return None


def _width_of(node) -> int | None:
    """Declared bit width of a port/signal node. None when it cannot be resolved.

    A node with no `width` is a scalar, i.e. 1 bit.
    """
    if node is None:
        return None
    width = getattr(node, "width", None)
    if width is None:
        return 1
    msb = _const_int(getattr(width, "msb", None))
    lsb = _const_int(getattr(width, "lsb", None))
    if msb is None or lsb is None:
        return None
    return abs(msb - lsb) + 1


def _extract_port_widths(module_def) -> dict[str, int]:
    """{port_name: width} for a module, covering both port declaration styles.

    ANSI style (`module m(input [7:0] a);`) carries the width on the port itself.
    Verilog-1995 style (`module m(a); input [7:0] a;`) carries it on a separate
    declaration in the module body, so both places are read.
    """
    widths: dict[str, int] = {}

    for item in module_def.portlist.ports:
        decl = item.first if isinstance(item, vast.Ioport) else None
        if decl is None:
            continue
        w = _width_of(decl)
        if w is not None and getattr(decl, "name", None):
            widths[decl.name] = w

    for item in (module_def.items or []):
        if not isinstance(item, vast.Decl):
            continue
        for child in (item.list or []):
            if isinstance(child, (vast.Input, vast.Output, vast.Inout)):
                w = _width_of(child)
                if w is not None and getattr(child, "name", None):
                    widths.setdefault(child.name, w)

    return widths


def _extract_signal_widths(module_def) -> dict[str, int]:
    """{signal_name: width} for the reg/wire declarations inside a testbench."""
    widths: dict[str, int] = {}
    for item in (module_def.items or []):
        if not isinstance(item, vast.Decl):
            continue
        for child in (item.list or []):
            if isinstance(child, (vast.Reg, vast.Wire, vast.Integer)):
                w = _width_of(child)
                if w is not None and getattr(child, "name", None):
                    widths.setdefault(child.name, w)
    return widths


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


# `@(posedge clk)` / `@(negedge clk)` used as an event control — the usual way a
# self-checking testbench synchronises from inside an initial block.
_EDGE_CONTROL_RE = re.compile(r"@\s*\(\s*(?:posedge|negedge)\b")


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


# ── Width-mismatch check ──────────────────────────────────────────────────────

def _check_port_widths(
    instances: list,
    dut_port_widths: dict[str, int],
    tb_signal_widths: dict[str, int],
    module_name: str,
) -> list[ErrorReportItem]:
    """Compare each DUT port's declared width against the testbench signal bound
    to it.

    A width mismatch is silent at simulation time — Verilog zero-extends or
    truncates without complaint — so the testbench compiles, runs, and reports
    wrong results. That makes it exactly the class of defect static analysis is
    for, and it cannot be found by the compiler.

    Only plain identifier connections are compared. A concatenation, a slice or
    an expression is skipped rather than guessed at.
    """
    errors: list[ErrorReportItem] = []
    seen: set[tuple[str, str]] = set()

    for inst in instances:
        for pa in (inst.portlist or []):
            portname = pa.portname
            argname = pa.argname
            if portname is None or argname is None:
                continue
            # Only a bare identifier has an unambiguous declared width.
            if not isinstance(argname, vast.Identifier):
                continue
            signal = argname.name

            port_w = dut_port_widths.get(portname)
            sig_w = tb_signal_widths.get(signal)
            if port_w is None or sig_w is None or port_w == sig_w:
                continue
            if (portname, signal) in seen:
                continue
            seen.add((portname, signal))

            errors.append(
                ErrorReportItem(
                    error_type=ErrorType.WIDTH_MISMATCH,
                    affected_signal=portname,
                    line=getattr(pa, "lineno", None),
                    suggested_fix=(
                        f"Port '{portname}' of {module_name} is {port_w} bit(s) "
                        f"wide but the testbench signal '{signal}' bound to it is "
                        f"{sig_w} bit(s). Verilog silently truncates or "
                        f"zero-extends, so this produces wrong values with no "
                        f"compiler warning. Declare '{signal}' as "
                        f"[{port_w - 1}:0]."
                    ),
                    severity=Severity.ERROR,
                )
            )

    return errors


# ── Clock-toggle check (SEQ) ─────────────────────────────────────────────────

def _dut_clock_ports(dut_verilog: str, dut_ports: list[tuple[str, str]]) -> list[str]:
    """DUT input ports that appear in an edge expression in the DUT itself.

    Derived from the DUT source rather than from a name convention, so a clock
    called `ck` or `pclk` is found and a data signal called `clock_enable` is not.
    """
    edged = set(re.findall(r"(?:pos|neg)edge\s+(\w+)", dut_verilog))
    inputs = {name for direction, name in dut_ports if direction in ("Input", "Inout")}
    return sorted(edged & inputs)


def _clock_is_toggled(tb_verilog: str, signal: str) -> bool:
    """Whether the testbench ever makes this signal change value repeatedly.

    Deliberately generous: any inversion, any assignment inside a repeating
    block, or more than one assignment anywhere counts as toggling. A clock that
    is assigned exactly once and never inverted is the only shape reported, so a
    correct-but-unusual clock generator is never flagged.
    """
    word = re.escape(signal)
    if re.search(rf"~\s*{word}\b", tb_verilog):
        return True
    if re.search(rf"\b{word}\s*<?=\s*~", tb_verilog):
        return True
    # An assignment inside an always/forever/repeat block re-runs by definition.
    for block in re.finditer(r"\b(?:always|forever|repeat)\b", tb_verilog):
        tail = tb_verilog[block.end():block.end() + 400]
        if re.search(rf"\b{word}\s*<?=", tail):
            return True
    assignments = re.findall(rf"\b{word}\s*<?=", tb_verilog)
    return len(assignments) > 1


def _check_clock_toggle(
    instances: list,
    dut_ports: list[tuple[str, str]],
    dut_verilog: str,
    tb_verilog: str,
) -> list[ErrorReportItem]:
    """A sequential DUT whose clock is initialised but never toggled.

    The simulation still compiles and runs; it simply never advances, so every
    scenario reports the reset value and the failure looks like a logic error
    rather than a missing clock. `_signal_is_driven` is satisfied by the initial
    assignment alone, so the undriven-input check cannot see this.
    """
    if not instances:
        return []

    inst = instances[0]
    port_to_signal: dict[str, str] = {}
    for pa in (inst.portlist or []):
        if pa.portname and pa.argname is not None and hasattr(pa.argname, "name"):
            port_to_signal[pa.portname] = pa.argname.name

    errors: list[ErrorReportItem] = []
    for clock_port in _dut_clock_ports(dut_verilog, dut_ports):
        signal = port_to_signal.get(clock_port, clock_port)
        if not re.search(rf"\b{re.escape(signal)}\s*<?=", tb_verilog):
            continue  # never assigned at all — that is the undriven-input check
        if _clock_is_toggled(tb_verilog, signal):
            continue
        errors.append(
            ErrorReportItem(
                error_type=ErrorType.CLOCK_NEVER_TOGGLED,
                affected_signal=clock_port,
                line=None,
                suggested_fix=(
                    f"Clock '{clock_port}' (testbench signal '{signal}') is "
                    "assigned once but never toggled, so no clock edge ever "
                    "occurs and the DUT never advances past its reset state. "
                    f"Add a generator: initial {signal} = 0; always #5 {signal} "
                    f"= ~{signal};"
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

def _check_sensitivity_lists(tb_module, tb_verilog: str) -> list[ErrorReportItem]:
    """
    For sequential circuits: verify the testbench synchronises to a clock edge
    somewhere.

    Two things this must NOT flag, both of which are ordinary correct style:

    1. A clock generator (`always #5 clk = ~clk;`) has no sensitivity list by
       design. Counting it as "an always-block with no edge trigger" flagged
       every testbench that generates its own clock — which is all of them.
    2. A self-checking testbench usually drives from an `initial` block and
       synchronises with `@(posedge clk)` event controls rather than with an
       edge-triggered `always`. That is edge synchronisation; it simply is not
       in a sensitivity list.

    So: ignore always-blocks that carry no sensitivity list at all, and accept
    an edge event control anywhere in the source as satisfying the check.
    """
    if _EDGE_CONTROL_RE.search(tb_verilog):
        return []

    always_blocks = [
        item for item in (tb_module.items or [])
        if isinstance(item, vast.Always)
    ]

    def _sens_entries(always_block) -> list:
        sens_list = getattr(always_block, "sens_list", None)
        if sens_list is None:
            return []
        return list(sens_list.list or [])

    # A delay-driven always (clock generator) has nothing to be sensitive to.
    triggered = [ab for ab in always_blocks if _sens_entries(ab)]
    if not triggered:
        return []

    def _has_edge_trigger(always_block) -> bool:
        for sens in _sens_entries(always_block):
            if getattr(sens, "type", None) in ("posedge", "negedge"):
                return True
        return False

    if any(_has_edge_trigger(ab) for ab in triggered):
        return []

    # Sensitised always-blocks exist, none is clock-triggered, and there is no
    # edge event control anywhere — the testbench really is not clock-synchronous.
    first_line = getattr(triggered[0], "lineno", None)
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

    # Only run the signal-level checks if port bindings look okay (avoid noise:
    # a mis-bound instance makes every downstream signal look wrong).
    if not port_errors:
        dataflow_errors = _check_driven_observed(instances, dut_ports, tb_verilog)
        port_errors = port_errors + _check_port_widths(
            instances,
            _extract_port_widths(dut_module),
            _extract_signal_widths(tb_module),
            module_name,
        )
    else:
        dataflow_errors = []

    sensitivity_errors: list[ErrorReportItem] = []
    fdisplay_missing: list[ErrorReportItem] = []
    if is_seq:
        sensitivity_errors = _check_sensitivity_lists(tb_module, tb_verilog)
        fdisplay_missing = _check_fdisplay(instances, dut_ports, tb_verilog)
        sensitivity_errors = sensitivity_errors + _check_clock_toggle(
            instances, dut_ports, dut_verilog, tb_verilog
        )
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
