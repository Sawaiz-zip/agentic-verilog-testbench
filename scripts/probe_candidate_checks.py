"""Can the two 'undetectable' fault classes actually be detected?

Two candidate checks, tested for recall on the injected faults and for false
positives on the 14 clean testbenches.
"""
import json, os, re, sys, glob, collections
sys.path.insert(0, '/Users/sawaiznaveed/Ilmenau Uni/ResearchProject')
os.chdir('/Users/sawaiznaveed/Ilmenau Uni/ResearchProject')
from pipeline.analysis.verilog_text import strip_noise
from pipeline.analysis import fault_injection as fi

FIX = {}
for d in ('cmb', 'seq'):
    for p in glob.glob(f'tests/fixtures/{d}/*_ref.v'):
        FIX[os.path.basename(p).replace('_ref.v', '')] = (p, d)

# one known-good testbench per circuit, exactly as the injection study builds it
TBS = {}
for s in ('final_hard_r1', 'weak_model_r1'):
    for f in glob.glob(f'results/{s}/*.json'):
        d = json.load(open(f))
        t = d.get('task_id')
        if t in FIX and d.get('eval1_pass') and t not in TBS:
            TBS[t] = d['driver_rtl']

print(f'clean testbenches available: {len(TBS)}  ({sum(1 for t in TBS if FIX[t][1]=="seq")} sequential)')
print()

# ---------- CANDIDATE CHECK A: sequential TB with no edge event control ----------
EDGE = re.compile(r'@\s*\(\s*(?:pos|neg)edge\b', re.I)

print('=' * 74)
print('CHECK A  "a sequential testbench that never waits on a clock edge"')
print('=' * 74)
fp = 0
seq = [t for t in TBS if FIX[t][1] == 'seq']
for t in seq:
    clean = strip_noise(TBS[t])
    n = len(EDGE.findall(clean))
    flag = n == 0
    if flag: fp += 1
    print(f'  clean {t:24s} edge-waits={n:2d}   {"FALSE POSITIVE" if flag else "ok"}')
print(f'\n  false positives on clean sequential testbenches: {fp} / {len(seq)}')

# recall: apply the real injector, then run the check
caught = tot = 0
for t in seq:
    dut = open(FIX[t][0]).read()
    for f_ in fi.inject_break_edge_sync(TBS[t], dut, t):
        tot += 1
        if len(EDGE.findall(strip_noise(f_.testbench))) == 0:
            caught += 1
print(f'  recall on break_edge_sync faults: {caught} / {tot}')

# ---------- CANDIDATE CHECK B: port bound to a signal named after another port ----
print()
print('=' * 74)
print('CHECK B  "port .X bound to a signal whose name is another port of the DUT"')
print('=' * 74)
def bindings(tb, mod):
    b = fi._bindings(tb, mod)
    return b or {}

fp2 = 0
for t in sorted(TBS):
    dut = open(FIX[t][0]).read()
    ports = set(fi._dut_port_directions(dut))
    b = bindings(strip_noise(TBS[t]), t)
    bad = [(p, sig) for p, sig in b.items()
           if sig in ports and sig != p]
    if bad: fp2 += 1
    print(f'  clean {t:24s} suspicious bindings={len(bad)}  {bad[:2] if bad else ""}')
print(f'\n  false positives on clean testbenches: {fp2} / {len(TBS)}')

caught2 = tot2 = 0
for t in sorted(TBS):
    dut = open(FIX[t][0]).read()
    ports = set(fi._dut_port_directions(dut))
    for f_ in fi.inject_swap_bindings(TBS[t], dut, t):
        tot2 += 1
        b = bindings(strip_noise(f_.testbench), t)
        if any(sig in ports and sig != p for p, sig in b.items()):
            caught2 += 1
print(f'  recall on swap_bindings faults: {caught2} / {tot2}')
