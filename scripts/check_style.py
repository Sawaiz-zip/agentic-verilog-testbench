#!/usr/bin/env python3
"""
Prose style checks against the rules in docs/report-writing-plan.md.

These are the habits that make academic prose read as machine-generated. The
check is advisory: it reports locations, it does not rewrite. Run per chapter.
"""
import pathlib
import re
import sys
import statistics

BANNED_OPENERS = ["Furthermore", "Moreover", "Additionally", "In addition",
                  "Notably", "Importantly", "Overall", "Consequently",
                  "It is important to note", "It should be noted", "It is worth noting"]
VAGUE = ["significantly", "substantially", "notably", "crucially", "considerably",
         "vastly", "remarkably", "extremely", "very high", "very low", "a wide range of",
         "cutting-edge", "state-of-the-art", "robustly", "seamlessly", "leverage"]
SUMMARY_TELLS = ["This demonstrates that", "This highlights", "Thus it can be seen",
                 "This underscores", "In summary,", "To summarise,", "This shows that"]

src = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "report.tex").read_text()
# body only, minus listings/verbatim/tables
body = src
for env in ["lstlisting", "verbatim", "tabular"]:
    body = re.sub(rf"\\begin\{{{env}\}}.*?\\end\{{{env}\}}", "", body, flags=re.S)
body = re.sub(r"(?<!\\)%.*", "", body)

issues = 0
paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()
         and not p.strip().startswith("\\") and len(p.split()) > 12]

print(f"prose paragraphs analysed: {len(paras)}")

for term in BANNED_OPENERS:
    for p in paras:
        if p.lstrip().startswith(term):
            print(f"  x banned opener '{term}': {p[:60]}...")
            issues += 1

low = body.lower()
for term in VAGUE:
    n = low.count(term.lower())
    if n:
        print(f"  x vague term '{term}' x{n}")
        issues += n

for term in SUMMARY_TELLS:
    n = body.count(term)
    if n:
        print(f"  x summary tell '{term}' x{n}")
        issues += n

dashes = body.count("---") + body.count("—")
words = len(body.split())
pages = max(1, words / 450)
if dashes / pages > 1.2:
    print(f"  x em-dashes: {dashes} over ~{pages:.0f} pp (limit ~1/page)")
    issues += 1
else:
    print(f"  . em-dashes: {dashes} over ~{pages:.0f} pp — within budget")

lens = [len(p.split()) for p in paras]
if lens:
    runs = 1
    worst = 1
    for a, b in zip(lens, lens[1:]):
        runs = runs + 1 if abs(a - b) <= 12 else 1
        worst = max(worst, runs)
    print(f"  . paragraph words: median {statistics.median(lens):.0f}, "
          f"range {min(lens)}-{max(lens)}, longest run of similar lengths: {worst}")
    if worst >= 4:
        print("    x four or more consecutive paragraphs of similar length")
        issues += 1

print(f"\n{'clean' if issues == 0 else str(issues) + ' issue(s)'}; ~{words} words, ~{pages:.1f} pp of prose")
