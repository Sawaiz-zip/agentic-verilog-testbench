"""
Deterministic fault injection for measuring the static localiser (RQ1, RQ2).

End-to-end pass rates cannot tell us whether the static layer works: a testbench
either passes or it does not, and when it fails we cannot tell which faults the
analyser *could* have caught. This module measures the analyser directly. Take a
testbench already known to pass, break it in one known way, and ask three
questions:

    does the static analyser flag it?   (our layer)
    does iverilog refuse to compile it? (the compiler baseline)
    does the simulation fail?           (the simulator baseline)

The three-way comparison is the evidence for RQ2 and RQ4. A fault only the static
analyser catches is a fault the existing tooling cannot find at all; a fault the
compiler already catches is one our layer adds nothing to.

Design rules, learned the hard way from four false positives in the analyser:

1. **A mutation must produce legal Verilog.** If the injector creates a syntax
   error then "the compiler caught it" is an artifact of the injector, not a
   property of the fault. Injectors that cannot mutate cleanly return None.
2. **Not-applicable is not a failure.** An injector that does not apply to a
   given testbench is excluded from the denominator and counted separately, so a
   detection rate is never inflated by cases that were never attempted.
3. **The mutation must actually change the source.** A no-op mutation that
   silently "passes" would report the unmutated testbench's verdict.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pipeline.analysis.error_taxonomy import ErrorType


@dataclass
class Fault:
    """One injected fault and the finding it ought to produce."""

    kind: str                    # injector name
    expected_type: str | None    # ErrorType value; None = not statically detectable
    signal: str                  # the port/signal the fault concerns
    description: str             # human-readable, for the report
    testbench: str               # the mutated source


# ── Source helpers ────────────────────────────────────────────────────────────

def _instance_block(tb: str, module_name: str) -> tuple[int, int] | None:
    """Character span of the DUT instantiation's port list, or None."""
    m = re.search(rf"\b{re.escape(module_name)}\s+\w+\s*\(", tb)
    if not m:
        return None
    depth = 0
    for i in range(m.end() - 1, len(tb)):
        if tb[i] == "(":
            depth += 1
        elif tb[i] == ")":
            depth -= 1
            if depth == 0:
                return m.end(), i
    return None


def _bindings(tb: str, module_name: str) -> dict[str, str]:
    """{port_name: bound_signal} for named connections in the DUT instance."""
    span = _instance_block(tb, module_name)
    if span is None:
        return {}
    body = tb[span[0]:span[1]]
    return {
        port: sig
        for port, sig in re.findall(r"\.\s*(\w+)\s*\(\s*(\w+)\s*\)", body)
    }


def _declared_width(tb: str, signal: str) -> tuple[int, int] | None:
    """(msb, lsb) of a reg/wire declaration, or None for a scalar/absent one."""
    m = re.search(
        rf"\b(?:reg|wire)\s*\[\s*(\d+)\s*:\s*(\d+)\s*\][^;]*\b{re.escape(signal)}\b",
        tb,
    )
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


_DIRECTION_RE = re.compile(r"\b(input|output|inout)\b")
_TYPE_WORDS = {"reg", "wire", "logic", "signed", "unsigned", "bit"}


def _dut_port_directions(dut: str) -> dict[str, str]:
    """{port: 'input'|'output'|'inout'} read from the DUT source.

    Handles both `input [7:0] a, input [7:0] b` on one line and the
    Verilog-1995 form where directions are declared in the module body. Each
    direction keyword owns the text up to the next direction keyword or the end
    of its declaration, with ranges and type words stripped, so a shared
    declaration like `output reg [7:0] result, output zero` resolves correctly.
    """
    text = re.sub(r"//[^\n]*", " ", dut)
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)

    directions: dict[str, str] = {}
    matches = list(_DIRECTION_RE.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        segment = text[m.end():end]
        # A declaration ends at a semicolon or at the close of the port list.
        stops = [p for p in (segment.find(";"), segment.find(")")) if p != -1]
        if stops:
            segment = segment[:min(stops)]
        segment = re.sub(r"\[[^\]]*\]", " ", segment)   # drop bit ranges
        for token in re.findall(r"\b\w+\b", segment):
            if token in _TYPE_WORDS or token[0].isdigit():
                continue
            directions.setdefault(token, m.group(1))
    return directions


def _dut_clock_ports(dut: str) -> list[str]:
    """DUT inputs that appear in an edge expression inside the DUT."""
    edged = set(re.findall(r"(?:pos|neg)edge\s+(\w+)", dut))
    directions = _dut_port_directions(dut)
    return sorted(p for p in edged if directions.get(p) == "input")


# ── Injectors ────────────────────────────────────────────────────────────────
# Each returns a list of Faults (one per eligible signal), possibly empty.

def inject_port_rename(tb: str, dut: str, module_name: str) -> list[Fault]:
    """Bind a port under a name the DUT does not have — the classic typo."""
    faults = []
    for port, sig in _bindings(tb, module_name).items():
        mutated = re.sub(
            rf"\.\s*{re.escape(port)}\s*\(\s*{re.escape(sig)}\s*\)",
            f".{port}_x({sig})",
            tb,
            count=1,
        )
        if mutated == tb:
            continue
        faults.append(Fault(
            kind="port_rename",
            expected_type=ErrorType.PORT_BINDING_MISMATCH.value,
            signal=port,
            description=f"port .{port} renamed to .{port}_x in the instantiation",
            testbench=mutated,
        ))
    return faults


def inject_port_drop(tb: str, dut: str, module_name: str) -> list[Fault]:
    """Leave a DUT port unconnected."""
    faults = []
    bindings = _bindings(tb, module_name)
    if len(bindings) < 2:
        return []
    for port, sig in bindings.items():
        # Remove the connection along with one adjacent comma, keeping the list legal.
        mutated = re.sub(
            rf",\s*\.\s*{re.escape(port)}\s*\(\s*{re.escape(sig)}\s*\)",
            "",
            tb,
            count=1,
        )
        if mutated == tb:
            mutated = re.sub(
                rf"\.\s*{re.escape(port)}\s*\(\s*{re.escape(sig)}\s*\)\s*,",
                "",
                tb,
                count=1,
            )
        if mutated == tb:
            continue
        faults.append(Fault(
            kind="port_drop",
            expected_type=ErrorType.PORT_BINDING_MISMATCH.value,
            signal=port,
            description=f"port .{port} left unconnected",
            testbench=mutated,
        ))
    return faults


def inject_width_change(tb: str, dut: str, module_name: str) -> list[Fault]:
    """Declare a bound testbench signal at the wrong width.

    Silent at simulation time — Verilog truncates or zero-extends without a
    warning — so this is the clearest case of a fault only static analysis can see.
    """
    faults = []
    for port, sig in _bindings(tb, module_name).items():
        width = _declared_width(tb, sig)
        if width is None:
            continue          # scalar or undeclared: no width to corrupt cleanly
        msb, lsb = width
        if msb - lsb < 1:
            continue          # [0:0] cannot be narrowed further
        new_msb = msb - 1
        mutated = re.sub(
            rf"(\b(?:reg|wire)\s*)\[\s*{msb}\s*:\s*{lsb}\s*\]([^;]*\b{re.escape(sig)}\b)",
            rf"\g<1>[{new_msb}:{lsb}]\g<2>",
            tb,
            count=1,
        )
        if mutated == tb:
            continue
        faults.append(Fault(
            kind="width_change",
            expected_type=ErrorType.WIDTH_MISMATCH.value,
            signal=port,
            description=(
                f"testbench signal '{sig}' narrowed from [{msb}:{lsb}] to "
                f"[{new_msb}:{lsb}] while port .{port} stays {msb - lsb + 1} bits"
            ),
            testbench=mutated,
        ))
    return faults


def inject_undriven_input(tb: str, dut: str, module_name: str) -> list[Fault]:
    """Stop driving a DUT input.

    Assignments are redirected to a fresh register rather than deleted, so the
    result is always syntactically valid — deleting a statement can empty an
    if-branch and produce a syntax error the compiler would then "catch",
    which would be an artifact of the injector.
    """
    faults = []
    directions = _dut_port_directions(dut)
    clocks = set(_dut_clock_ports(dut))
    for port, sig in _bindings(tb, module_name).items():
        if directions.get(port) != "input" or port in clocks:
            continue
        assign_re = re.compile(rf"\b{re.escape(sig)}\s*(<=|=)(?!=)")
        if not assign_re.search(tb):
            continue
        sink = f"{sig}_sink"
        width = _declared_width(tb, sig)
        decl = (
            f"  reg [{width[0]}:{width[1]}] {sink};\n" if width
            else f"  reg {sink};\n"
        )
        mutated = assign_re.sub(lambda m: f"{sink} {m.group(1)}", tb)
        # Declare the sink immediately after the module header.
        header = re.search(r"\bmodule\b[^;]*;", mutated)
        if header is None or mutated == tb:
            continue
        mutated = mutated[:header.end()] + "\n" + decl + mutated[header.end():]
        faults.append(Fault(
            kind="undriven_input",
            expected_type=ErrorType.UNDRIVEN_INPUT.value,
            signal=port,
            description=f"DUT input .{port} is declared and bound but never assigned",
            testbench=mutated,
        ))
    return faults


def inject_unobserved_output(tb: str, dut: str, module_name: str) -> list[Fault]:
    """Stop checking a DUT output — the testbench then passes by not looking.

    Only applied where the output participates in a conjunction that can be
    removed cleanly; otherwise the injector declines rather than risk mangling
    the source.
    """
    faults = []
    directions = _dut_port_directions(dut)
    for port, sig in _bindings(tb, module_name).items():
        if directions.get(port) not in ("output", "inout"):
            continue
        w = re.escape(sig)
        # `&& sig === val`  or  `sig === val &&`
        patterns = [
            rf"\s*&&\s*{w}\s*[=!]==?\s*[^\s&|)]+",
            rf"{w}\s*[=!]==?\s*[^\s&|)]+\s*&&\s*",
        ]
        mutated = tb
        for pat in patterns:
            candidate = re.sub(pat, "", mutated)
            if candidate != mutated:
                mutated = candidate
        if mutated == tb:
            continue
        # The signal must no longer be observed anywhere for the fault to be real.
        if re.search(rf"{w}\s*[=!]==?", mutated) or re.search(
            rf"\$(?:display|monitor|write|fdisplay)[^;]*\b{w}\b", mutated
        ):
            continue
        faults.append(Fault(
            kind="unobserved_output",
            expected_type=None,   # resolved by the caller: SEQ reports missing_fdisplay
            signal=port,
            description=f"DUT output .{port} is never compared or printed",
            testbench=mutated,
        ))
    return faults


def inject_remove_clock_generator(tb: str, dut: str, module_name: str) -> list[Fault]:
    """Delete the clock generator, leaving the clock assigned once and never toggled.

    The simulation still compiles and runs; it simply never advances, so every
    scenario reads back the reset value.
    """
    faults = []
    for clock in _dut_clock_ports(dut):
        sig = _bindings(tb, module_name).get(clock, clock)
        w = re.escape(sig)
        mutated = tb
        for pat in (
            rf"^[ \t]*always\s*#\d+\s*{w}\s*<?=\s*~\s*{w}\s*;[ \t]*\n",
            rf"^[ \t]*initial\s+forever\s*#\d+\s*{w}\s*<?=\s*~\s*{w}\s*;[ \t]*\n",
            rf"^[ \t]*always\s+#\d+\s+{w}\s*<?=\s*~{w}\s*;[ \t]*\n",
        ):
            mutated = re.sub(pat, "", mutated, flags=re.MULTILINE)
        if mutated == tb:
            continue
        # A surviving toggle means the fault was not actually injected.
        if re.search(rf"~\s*{w}\b", mutated):
            continue
        faults.append(Fault(
            kind="remove_clock_generator",
            expected_type=ErrorType.CLOCK_NEVER_TOGGLED.value,
            signal=clock,
            description=f"clock generator for '{sig}' deleted; no edge ever occurs",
            testbench=mutated,
        ))
    return faults


def inject_break_edge_sync(tb: str, dut: str, module_name: str) -> list[Fault]:
    """Replace every clock-edge wait with a bare delay.

    The testbench then drives a sequential DUT without synchronising to it —
    a race against the clock rather than a defined ordering.
    """
    if not _dut_clock_ports(dut):
        return []
    mutated, n = re.subn(r"@\s*\(\s*(?:pos|neg)edge\s+\w+\s*\)", "#10", tb)
    if n == 0 or mutated == tb:
        return []
    return [Fault(
        kind="break_edge_sync",
        expected_type=ErrorType.SENSITIVITY_LIST_ERROR.value,
        signal="(clock)",
        description=f"all {n} clock-edge waits replaced with bare #10 delays",
        testbench=mutated,
    )]


def inject_swap_bindings(tb: str, dut: str, module_name: str) -> list[Fault]:
    """Swap two same-direction, same-width input bindings.

    NEGATIVE CONTROL. Both connections remain legal and correctly typed, so no
    structural check can see this — it is a semantic error. Included to mark the
    honest boundary of what static analysis can do, and to show the simulator
    catching what the analyser cannot.
    """
    directions = _dut_port_directions(dut)
    clocks = set(_dut_clock_ports(dut))
    bindings = _bindings(tb, module_name)
    inputs = [
        (p, s) for p, s in bindings.items()
        if directions.get(p) == "input" and p not in clocks
    ]
    for i in range(len(inputs)):
        for j in range(i + 1, len(inputs)):
            (pa, sa), (pb, sb) = inputs[i], inputs[j]
            if _declared_width(tb, sa) != _declared_width(tb, sb):
                continue
            mutated = tb
            mutated = re.sub(rf"\.\s*{re.escape(pa)}\s*\(\s*{re.escape(sa)}\s*\)",
                             f".{pa}(__SWAP__)", mutated, count=1)
            mutated = re.sub(rf"\.\s*{re.escape(pb)}\s*\(\s*{re.escape(sb)}\s*\)",
                             f".{pb}({sa})", mutated, count=1)
            mutated = mutated.replace("__SWAP__", sb)
            if mutated == tb:
                continue
            return [Fault(
                kind="swap_bindings",
                expected_type=None,      # deliberately undetectable statically
                signal=f"{pa}/{pb}",
                description=(
                    f"inputs .{pa} and .{pb} bound to each other's signals "
                    "(semantic fault, structurally legal)"
                ),
                testbench=mutated,
            )]
    return []


INJECTORS = [
    inject_port_rename,
    inject_port_drop,
    inject_width_change,
    inject_undriven_input,
    inject_unobserved_output,
    inject_remove_clock_generator,
    inject_break_edge_sync,
    inject_swap_bindings,
]


def inject_all(tb: str, dut: str, module_name: str) -> list[Fault]:
    """Every fault that can be injected cleanly into this testbench."""
    faults: list[Fault] = []
    is_seq = bool(_dut_clock_ports(dut))
    for injector in INJECTORS:
        for fault in injector(tb, dut, module_name):
            # An unobserved sequential output is reported under the SEQ-specific
            # class; the combinational one under the general class.
            if fault.kind == "unobserved_output" and fault.expected_type is None:
                fault.expected_type = (
                    ErrorType.MISSING_FDISPLAY.value if is_seq
                    else ErrorType.UNOBSERVED_OUTPUT.value
                )
            faults.append(fault)
    return faults
