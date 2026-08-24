"""
Text preparation for the source-level heuristics in the static analyser.

Several checks ask questions of the raw testbench text — is this signal ever
assigned, is it ever compared or printed, is the clock ever toggled. Asked of raw
source, all of them can be answered by text that is not code:

    $display("PASS: addition_boundary_overflow");   // "overflow" is a scenario name
    $fdisplay(f, "clk=%b out=%b", clk, out);        // "clk=" is a format string
    // remember to check overflow                    // a comment

Each of those made a check believe a signal was observed, driven, or toggled when
it was not — a false negative that hides a real defect. The same class of defect
was found in the Eval1 verdict, where a scenario named `immediate_mismatch`
failed its own run.

Blanking preserves length and line structure, so any offset or line number taken
from the prepared text still refers to the same place in the original.
"""

import re

# A string literal, tolerating escaped quotes; or a line/block comment.
_NOISE = re.compile(
    r'"(?:\\.|[^"\\])*"'      # "..." with \" escapes
    r"|//[^\n]*"              # // to end of line
    r"|/\*.*?\*/",            # /* ... */
    re.DOTALL,
)


def _blank(match: re.Match) -> str:
    """Replace a match with spaces, keeping newlines so line numbers hold."""
    text = match.group(0)
    if text.startswith('"'):
        # Keep the quotes so the token still reads as a string in context.
        return '"' + "".join("\n" if c == "\n" else " " for c in text[1:-1]) + '"'
    return "".join("\n" if c == "\n" else " " for c in text)


def strip_noise(source: str) -> str:
    """Return `source` with comment and string-literal *contents* blanked.

    Same length, same line breaks — only the characters that are not code are
    replaced by spaces. A `$display("out=%b", out)` keeps its `out` argument,
    which is the real observation; the `out` inside the format string does not
    survive, which is the false one.
    """
    if not source:
        return source
    return _NOISE.sub(_blank, source)
