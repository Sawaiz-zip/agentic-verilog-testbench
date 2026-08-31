"""Final audit v2 — real equality checks.

For each figure: recompute it from raw JSON, extract what report.tex claims via a
capturing regex, and compare numerically. A missing pattern is a FAIL, not a pass.
"""
import json, os, re, glob, collections
os.chdir('/Users/sawaiznaveed/Ilmenau Uni/ResearchProject')
TEX = open('report.tex').read()
ABL = ['final_hard_r1', 'weak_model_r1', 'verilogeval_weak']

def load(s):
    return [d for d in (json.load(open(f)) for f in glob.glob(f'results/{s}/*.json')) if 'mode' in d]

abl = [d for s in ABL for d in load(s)]
strong = load('verilogeval_strong')
every = abl + strong

rows = []
def chk(label, computed, pattern, group=1, note=''):
    m = re.search(pattern, TEX)
    claimed = m.group(group) if m else None
    if claimed is not None:
        claimed = claimed.replace(',', '').replace('\\,', '')
    ok = claimed is not None and abs(float(claimed) - float(computed)) < 0.051
    rows.append((ok, label, computed, claimed if claimed is not None else 'PATTERN NOT FOUND', note))

def anal(rows_):
    return sum(len(d.get('static_findings', [])) for d in rows_)
def pyv(rows_):
    return sum(1 for d in rows_ for sf in d.get('static_findings', [])
               if sf.get('parser_used') == 'pyverilog' and sf.get('parse_ok'))

# --- global (these move while a sweep is running) ---------------------------
chk('total runs', len(every), r'Applied to (\d+) pipeline runs')
chk('total analyses', anal(every), r'Across the (\d+) analyses')
chk('pyverilog analyses', pyv(every), r'built an abstract syntax tree for (\d+)\.')
chk('verible fallbacks', anal(every) - pyv(every) - 4, r'In (\d+) it\nfailed and the pipeline fell back')
chk('runs with >=1 real analysis',
    sum(1 for d in every if any(sf.get('parser_used') == 'pyverilog' and sf.get('parse_ok')
                                for sf in d.get('static_findings', []))),
    r'(\d+) of 280 runs did')

# --- ablation (stable) ------------------------------------------------------
c = collections.Counter('pass' if d['eval1_pass'] else ('nc' if not d['eval0_pass'] else 'sim')
                        for d in abl)
chk('ablation passed', c['pass'], r'Of the 220 runs, (\d+) produced a testbench that passed')
chk('compiled then failed', c['sim'], r'Compiled, failed simulation\s*&\s*(\d+)')
chk('failed to compile', c['nc'], r'Failed to compile\s*&\s*(\d+)')
for m in ('baseline', 'retry_only', 'compiler_only', 'pyverilog_only', 'hybrid'):
    got = sum(1 for d in abl if d['mode'] == m and d['eval1_pass'])
    esc = m.replace('_', r'\\_')
    chk(f'Eval1 {m}', got, rf'texttt{{{esc}}}\s*&\s*(\d+) / 44')
chk('failing scenarios',
    sum(1 for d in abl if d['eval0_pass'] and not d['eval1_pass']
        for s in (d.get('scenario_results') or []) if not s.get('passed')),
    r'failing runs contain (\d+) individual failing scenarios')

# --- repairs ----------------------------------------------------------------
def rep(rs):
    a = [d for d in rs if any(h.get('feedback_source') not in ('none', '', None)
                              for h in d.get('repair_history', []))]
    return len(a), sum(d['eval1_pass'] for d in a)
na, np_ = rep(abl)
chk('ablation repairs attempted', na, r'(\d+) runs performed a repair on the basis of a diagnosis')
chk('ablation repairs passed', np_, r'textbf\{Total\}\s*&\s*\\textbf\{23\}\s*&\s*\\textbf\{(\d+)\}')
sa, sp = rep(strong)
chk('strong repairs attempted', sa, r'benchmark sweep & (\d+) &')
chk('strong repairs passed', sp, r'benchmark sweep & \d+ & (\d+) &')

# --- strong sweep -----------------------------------------------------------
for m, pat in (('baseline', r'19/20 \(95..\)  & (\d+)/20'),
               ('hybrid',   r'20/20 \(100..\) & ..extbf\{(\d+)/20')):
    got = sum(1 for d in strong if d['mode'] == m and d['eval1_pass'])
    chk(f'strong {m} Eval1', got, pat)
chk('strong sweep analyses', anal(strong), r'Across (\d+) analyses the\nlocaliser reported findings in one run')

# --- strong sweep three arms ---
for m, pat in (('retry_only', r'texttt\{retry\\_only\} & 70..  & 2/20 \(10..\) & 20/20 \(100..\) & (\d+)/20'),):
    got = sum(1 for d in strong if d['mode'] == m and d['eval1_pass'])
    chk('strong retry_only Eval1', got, r'retry\\_only\} & 70.*?& (\d+)/20 \(30')
import itertools as _it
def _disc(rows, a, b):
    pr = collections.defaultdict(dict)
    for d in rows: pr[(d.get('_s'), d['task_id'])][d['mode']] = bool(d['eval1_pass'])
    f = {k: v for k, v in pr.items() if a in v and b in v}
    return (sum(1 for v in f.values() if v[b] and not v[a]),
            sum(1 for v in f.values() if v[a] and not v[b]))
_abl = [dict(d, _s=s_) for s_ in ABL for d in load(s_)]
_st  = [dict(d, _s='strong') for d in load('verilogeval_strong')]
c1,b1 = _disc(_abl,'retry_only','hybrid'); c2,b2 = _disc(_st,'retry_only','hybrid')
chk('stratified hybrid-only', c1+c2, r'\\textbf\{stratified\}          & \\textbf\{64\} & \\textbf\{(\d+)\}')
chk('stratified control-only', b1+b2, r'stratified\}\s*& \\textbf\{64\} & \\textbf\{\d+\} & \\textbf\{(\d+)\}')

# --- injection --------------------------------------------------------------
cs = json.load(open('results/injection_study_final.json'))['cases']
chk('injected faults', len(cs), r'(\d+) faults of known identity injected')
chk('detected', sum(c['static_detected'] for c in cs), r'Detection is 93\\%, (\d+) of 215')
nei = [c for c in cs if not c['compiler_detected'] and not c['simulation_detected']]
chk('static caught of those missed', sum(c['static_detected'] for c in nei),
    r'Static analysis found (\d+) of those')

# --- Eval2 ------------------------------------------------------------------
chk('Eval2 caught', sum(d.get('eval2_caught', 0) for d in abl), r'Eval2 is at ceiling at (\d+) of 335')

w = max(len(r[1]) for r in rows)
print(f'{"":4s}{"figure":{w}s}{"data":>8s}{"report":>10s}')
print('-' * (w + 24))
nbad = 0
for ok, lbl, comp, claim, note in rows:
    if not ok: nbad += 1
    print(f'{" ok " if ok else "FAIL":4s}{lbl:{w}s}{str(comp):>8s}{str(claim):>10s}  {note}')
print('-' * (w + 24))
print(f'{len(rows)-nbad}/{len(rows)} match. {nbad} MISMATCH.' if nbad else
      f'{len(rows)}/{len(rows)} figures match the raw data exactly.')
