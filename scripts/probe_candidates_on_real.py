"""Would the two candidate checks have fired on REAL generated testbenches?

The injection study says they work on faults we planted. This asks the question that
actually matters: do those faults occur in the wild?
"""
import json, os, re, sys, glob, collections
sys.path.insert(0, '/Users/sawaiznaveed/Ilmenau Uni/ResearchProject')
os.chdir('/Users/sawaiznaveed/Ilmenau Uni/ResearchProject')
from pipeline.analysis.verilog_text import strip_noise
from pipeline.analysis import fault_injection as fi

SWEEPS = ['final_hard_r1', 'weak_model_r1', 'verilogeval_weak', 'verilogeval_strong']
runs = []
for s in SWEEPS:
    for f in glob.glob(f'results/{s}/*.json'):
        d = json.load(open(f))
        if 'mode' in d:
            d['_sweep'] = s
            runs.append(d)
print(f'real runs examined: {len(runs)}')

EDGE = re.compile(r'@\s*\(\s*(?:pos|neg)edge\b', re.I)

# ---------------- CHECK A ----------------
seq = [d for d in runs if d.get('circuit_type') == 'SEQ' and (d.get('driver_rtl') or '').strip()]
firesA = [d for d in seq if len(EDGE.findall(strip_noise(d['driver_rtl']))) == 0]
print()
print('=' * 76)
print('CHECK A — sequential testbench that never waits on a clock edge')
print('=' * 76)
print(f'  sequential testbenches in the wild : {len(seq)}')
print(f'  would the check FIRE               : {len(firesA)}  ({len(firesA)/len(seq)*100:.1f}%)')
if firesA:
    byo = collections.Counter((d['_sweep'], d['task_id']) for d in firesA)
    for (sw, t), n in byo.most_common(12):
        ex = [d for d in firesA if d['_sweep'] == sw and d['task_id'] == t][0]
        print(f'     {sw:20s} {t[:26]:27s} mode={ex["mode"]:14s} eval1={ex["eval1_pass"]}')
    passing = sum(1 for d in firesA if d['eval1_pass'])
    print(f'  of those, how many PASSED Eval1    : {passing}   <- these would be FALSE POSITIVES')
    print(f'  of those, how many FAILED          : {len(firesA)-passing}  <- genuine catches')

# ---------------- CHECK B ----------------
print()
print('=' * 76)
print('CHECK B — port bound to a signal named after a DIFFERENT port')
print('=' * 76)
firesB = []
usable = 0
for d in runs:
    tb, dut, mod = d.get('driver_rtl') or '', d.get('dut_rtl') or '', d.get('module_name') or ''
    if not tb.strip() or not dut.strip():
        continue
    try:
        ports = set(fi._dut_port_directions(dut))
        b = fi._bindings(strip_noise(tb), mod) or {}
    except Exception:
        continue
    if not ports or not b:
        continue
    usable += 1
    bad = [(p, sg) for p, sg in b.items() if sg in ports and sg != p]
    if bad:
        firesB.append((d, bad))
print(f'  testbenches where the check could run : {usable}')
print(f'  would the check FIRE                  : {len(firesB)}  ({len(firesB)/usable*100:.1f}%)')
for d, bad in firesB[:12]:
    print(f'     {d["_sweep"]:20s} {d["task_id"][:24]:25s} mode={d["mode"]:14s} '
          f'eval1={str(d["eval1_pass"]):5s} {bad[:2]}')
if firesB:
    passing = sum(1 for d, _ in firesB if d['eval1_pass'])
    print(f'  of those, how many PASSED Eval1       : {passing}   <- FALSE POSITIVES')
    print(f'  of those, how many FAILED             : {len(firesB)-passing}  <- genuine catches')

print()
print('=' * 76)
print('BOTTOM LINE')
print('=' * 76)
tot = len(firesA) + len(firesB)
print(f'  extra findings the two candidate checks would add across 280 runs: {tot}')
print(f'  existing six checks found: 3 runs')
