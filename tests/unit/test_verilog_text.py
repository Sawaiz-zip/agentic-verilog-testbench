"""
strip_noise blanks the parts of a testbench that are text rather than code.

Offsets must survive: several callers find a match in the prepared text and then
edit the original at those positions, so length and line breaks have to be
identical.
"""

from pipeline.analysis.verilog_text import strip_noise


def test_length_and_line_structure_are_preserved():
    src = 'module tb;\n  initial $display("hello world");  // a comment\nendmodule\n'
    out = strip_noise(src)
    assert len(out) == len(src)
    assert out.count("\n") == src.count("\n")


def test_string_contents_are_blanked_but_arguments_survive():
    src = '$fdisplay(f, "clk=%b out=%b", clk, out);'
    out = strip_noise(src)
    assert "clk=%b" not in out       # the format string is gone
    assert ", clk, out)" in out      # the real arguments remain


def test_comments_are_blanked():
    assert "overflow" not in strip_noise("// remember to check overflow\n")
    assert "overflow" not in strip_noise("/* check\n   overflow */\n")


def test_block_comment_keeps_its_newlines():
    src = "a\n/* one\n   two */\nb\n"
    out = strip_noise(src)
    assert out.count("\n") == src.count("\n")
    assert len(out) == len(src)


def test_escaped_quote_does_not_end_the_string_early():
    src = r'$display("she said \"overflow\" loudly"); y = 1;'
    out = strip_noise(src)
    assert "overflow" not in out
    assert "y = 1;" in out           # code after the string is untouched


def test_code_outside_strings_is_untouched():
    src = "assign y = a & b;  // and gate\n"
    assert strip_noise(src).startswith("assign y = a & b;")


def test_empty_input():
    assert strip_noise("") == ""
