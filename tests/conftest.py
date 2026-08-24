"""
Shared test fixtures.

`fake_llm` monkeypatches the `llm_call` symbol imported into every node module
so the entire pipeline runs offline with canned responses — ZERO API tokens.
Canned responses are keyed by the `node` argument, so one graph run traverses
the whole pipeline deterministically.
"""

import pytest

# Node modules that do `from pipeline.llm import llm_call` (name bound locally,
# so each must be patched individually).
_LLM_NODE_MODULES = [
    "pipeline.nodes.classify",
    "pipeline.nodes.gen_dut",
    "pipeline.nodes.extract_spec",
    "pipeline.nodes.gen_scenarios",
    "pipeline.nodes.gen_driver",
    "pipeline.nodes.gen_checker",
    "pipeline.nodes.error_reasoner",
    "pipeline.nodes.repair",
    "pipeline.eval.mutant_gen",
]

# A minimal but real, compilable half-adder DUT + testbench.
_CANNED_DUT = """module top_module(input a, input b, output sum, output cout);
  assign sum = a ^ b;
  assign cout = a & b;
endmodule
"""

_CANNED_DRIVER = """module testbench;
  reg a, b;
  wire sum, cout;
  top_module uut(.a(a), .b(b), .sum(sum), .cout(cout));
  initial begin
    a=0; b=0; #10;
    if (sum===0 && cout===0) $display("PASS: zero"); else $display("FAIL: zero");
    a=1; b=1; #10;
    if (sum===0 && cout===1) $display("PASS: both"); else $display("FAIL: both");
    $finish;
  end
endmodule
"""

_CANNED_SPEC = (
    '{"ports": {"inputs": [{"name": "a", "width": 1, "description": "x"},'
    '{"name": "b", "width": 1, "description": "y"}],'
    '"outputs": [{"name": "sum", "width": 1, "description": "s"},'
    '{"name": "cout", "width": 1, "description": "c"}],'
    '"clock": null, "reset": null}, "behaviour": "half adder",'
    '"timing": "combinational", "edge": null}'
)

_CANNED_SCENARIOS = (
    '[{"name": "zero", "inputs": {"a": 0, "b": 0}, "expected": {"sum": 0, "cout": 0}},'
    '{"name": "both", "inputs": {"a": 1, "b": 1}, "expected": {"sum": 0, "cout": 1}}]'
)

# A DISTINCT (but still valid) testbench returned by repair, so driver-identity
# oscillation does not trigger spuriously in success tests.
_CANNED_DRIVER_FIXED = _CANNED_DRIVER.replace(
    'if (sum===0 && cout===1) $display("PASS: both");',
    'if (sum===0 && cout===1) $display("PASS: both"); // repaired',
)

_CANNED_BY_NODE = {
    "classify": '{"circuit_type": "CMB"}',
    "gen_dut": _CANNED_DUT,
    "extract_spec": _CANNED_SPEC,
    "gen_scenarios": _CANNED_SCENARIOS,
    "gen_driver": _CANNED_DRIVER,
    "gen_checker": "def check(out):\n    return True\n",
    "gen_mutant": _CANNED_DUT.replace("a & b", "a | b"),  # a real fault
    "error_reasoner": "[]",
    "repair": _CANNED_DRIVER_FIXED,
}


# ── Sequential (SEQ) canned responses ─────────────────────────────────────────
_CANNED_SEQ_DUT = (
    "module dff(input clk, input d, output reg q);\n"
    "  always @(posedge clk) q <= d;\n"
    "endmodule\n"
)
# Driver that instantiates the DUT but does NOT observe q and does NOT toggle clk,
# so the standardiser visibly acts (inserts $monitor + clock).
_CANNED_SEQ_DRIVER = (
    "module testbench;\n"
    "  reg clk, d; wire q;\n"
    "  dff uut(.clk(clk), .d(d), .q(q));\n"
    "  initial begin clk=0; d=1; #10; d=0; #10; $finish; end\n"
    "endmodule\n"
)
_CANNED_SEQ_SPEC = (
    '{"ports": {"inputs": [{"name":"clk","width":1},{"name":"d","width":1}],'
    '"outputs": [{"name":"q","width":1}], "clock": "clk", "reset": null},'
    '"behaviour": "d flip-flop", "timing": "synchronous", "edge": "posedge"}'
)
_CANNED_SEQ = {
    "classify": '{"circuit_type": "SEQ"}',
    "gen_dut": _CANNED_SEQ_DUT,
    "extract_spec": _CANNED_SEQ_SPEC,
    "gen_scenarios": '[{"name":"load1","inputs":{"d":1},"expected":{"q":1}}]',
    "gen_driver": _CANNED_SEQ_DRIVER,
    "gen_checker": "def check(o):\n    return True\n",
    "gen_mutant": _CANNED_SEQ_DUT.replace("q <= d", "q <= ~d"),
    "error_reasoner": "[]",
    "repair": _CANNED_SEQ_DRIVER,
}


def _make_fake_llm(overrides=None):
    responses = dict(_CANNED_BY_NODE)
    if overrides:
        responses.update(overrides)

    def fake_llm_call(*, node, model, prompt, run_id, max_tokens=4096,
                     max_retries=3, temperature=None):
        text = responses.get(node, "")
        log = {
            "node": node,
            "model": model,
            "provider": "fake",
            "run_id": run_id,
            "temperature": 0.7 if temperature is None else float(temperature),
            "tokens_in": 10,
            "tokens_out": 5,
            "latency_ms": 1,
            "rate_limit_retries": 0,
        }
        return text, log

    return fake_llm_call


@pytest.fixture
def fake_llm(monkeypatch):
    """Patch llm_call in every node module with canned, offline responses."""
    import importlib
    fake = _make_fake_llm()
    for mod_name in _LLM_NODE_MODULES:
        mod = importlib.import_module(mod_name)
        monkeypatch.setattr(mod, "llm_call", fake, raising=True)
    return fake


@pytest.fixture
def fake_llm_seq(monkeypatch):
    """Install SEQ-coherent canned responses (clocked DUT, spec with a clock, and a
    driver missing $monitor so the standardiser acts)."""
    import importlib
    fake = _make_fake_llm(_CANNED_SEQ)
    for mod_name in _LLM_NODE_MODULES:
        mod = importlib.import_module(mod_name)
        monkeypatch.setattr(mod, "llm_call", fake, raising=True)
    return fake


@pytest.fixture
def fake_llm_factory(monkeypatch):
    """Like fake_llm but lets a test override specific node responses."""
    import importlib

    def _install(overrides=None):
        fake = _make_fake_llm(overrides)
        for mod_name in _LLM_NODE_MODULES:
            mod = importlib.import_module(mod_name)
            monkeypatch.setattr(mod, "llm_call", fake, raising=True)
        return fake

    return _install


@pytest.fixture
def mock_icarus(monkeypatch):
    """Mock Icarus so evaluate_node runs without invoking iverilog/vvp."""
    from pipeline.eval import icarus

    monkeypatch.setattr(icarus, "compile_tb",
                       lambda drv, dut, timeout_s=30: (True, "", "/tmp/fake.out"))
    monkeypatch.setattr(icarus, "simulate_tb",
                       lambda path, timeout_s=30: (True, "PASS: zero\nPASS: both\n"))
    monkeypatch.setattr(icarus, "eval2",
                       lambda drv, muts, timeout_s=30: 1.0)
    monkeypatch.setattr(icarus, "eval2_detailed",
                       lambda drv, muts, timeout_s=30: (1.0, len(muts), len(muts), len(muts)))
    # evaluate_node imports these names into its own module namespace too
    import pipeline.nodes.evaluate as ev
    monkeypatch.setattr(ev.icarus, "compile_tb",
                       lambda drv, dut, timeout_s=30: (True, "", "/tmp/fake.out"))
    monkeypatch.setattr(ev.icarus, "simulate_tb",
                       lambda path, timeout_s=30: (True, "PASS: zero\nPASS: both\n"))
    monkeypatch.setattr(ev.icarus, "eval2",
                       lambda drv, muts, timeout_s=30: 1.0)
    monkeypatch.setattr(ev.icarus, "eval2_detailed",
                       lambda drv, muts, timeout_s=30: (1.0, len(muts), len(muts), len(muts)))
    # The fake compiled path ("/tmp/fake.out") won't exist, so evaluate's cleanup
    # (os.path.exists → unlink) is naturally a no-op — no global os patch needed.


@pytest.fixture
def mock_icarus_flaky(monkeypatch):
    """Scriptable Icarus mock. Returns a controller with `.sim_results` — a list
    of (passed, output) tuples consumed one per simulate call (last repeats).
    Use to drive the repair loop: e.g. [FAIL, PASS] = repaired on 2nd try."""
    import pipeline.nodes.evaluate as ev

    class _Ctl:
        sim_results = [(True, "PASS: zero\nPASS: both\n")]
        compile_ok = True

    ctl = _Ctl()
    calls = {"sim": 0}

    def _compile(drv, dut, timeout_s=30):
        return (ctl.compile_ok, "" if ctl.compile_ok else "syntax error", "/tmp/f.out")

    def _sim(path, timeout_s=30):
        i = min(calls["sim"], len(ctl.sim_results) - 1)
        calls["sim"] += 1
        return ctl.sim_results[i]

    monkeypatch.setattr(ev.icarus, "compile_tb", _compile)
    monkeypatch.setattr(ev.icarus, "simulate_tb", _sim)
    monkeypatch.setattr(ev.icarus, "eval2", lambda drv, muts, timeout_s=30: 1.0)
    monkeypatch.setattr(
        ev.icarus, "eval2_detailed",
        lambda drv, muts, timeout_s=30: (1.0, len(muts), len(muts), len(muts)),
    )
    return ctl
