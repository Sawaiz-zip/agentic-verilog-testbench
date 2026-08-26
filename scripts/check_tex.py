#!/usr/bin/env python3
"""
Structural checks on report.tex that do not need a TeX installation.

Compilation is the real test, but it is not always available, and most errors
that break a build are detectable from the source alone: unbalanced groups,
mismatched environments, references to labels that do not exist, and citations
to keys with no bibitem.
"""
import pathlib
import re
import sys

src = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "report.tex").read_text()
errs, warns = [], []

# Braces, ignoring escaped ones and the contents of verbatim-ish listings.
stripped = re.sub(r"(?<!\\)%.*", "", src)
stripped = re.sub(r"\\[{}]", "", stripped)
if stripped.count("{") != stripped.count("}"):
    errs.append(f"unbalanced braces: {stripped.count('{')} open, {stripped.count('}')} close")

# Environments
begins = re.findall(r"\\begin\{(\w+\*?)\}", stripped)
ends = re.findall(r"\\end\{(\w+\*?)\}", stripped)
for env in set(begins) | set(ends):
    if begins.count(env) != ends.count(env):
        errs.append(f"environment '{env}': {begins.count(env)} begin, {ends.count(env)} end")

# Labels and references
labels = set(re.findall(r"\\label\{([^}]+)\}", stripped))
refs = set(re.findall(r"\\(?:ref|autoref|nameref)\{([^}]+)\}", stripped))
for r in sorted(refs - labels):
    errs.append(f"\\ref to undefined label: {r}")
dupes = [l for l in labels if len(re.findall(r"\\label\{" + re.escape(l) + r"\}", stripped)) > 1]
for d in sorted(set(dupes)):
    errs.append(f"duplicate label: {d}")

# Citations
keys = set(re.findall(r"\\bibitem\{([^}]+)\}", stripped))
cites = set()
for c in re.findall(r"\\cite\{([^}]+)\}", stripped):
    cites.update(k.strip() for k in c.split(","))
for c in sorted(cites - keys):
    errs.append(f"\\cite to missing bibitem: {c}")
for k in sorted(keys - cites):
    warns.append(f"bibitem never cited: {k}")

# Structure report
chapters = re.findall(r"\\chapter\{([^}]+)\}", stripped)
print(f"chapters : {len(chapters)}")
for i, c in enumerate(chapters, 1):
    n = len(re.findall(r"\\section\{", stripped.split(r"\chapter{" + c + "}")[-1].split(r"\chapter{")[0]))
    print(f"  {i}. {c}  ({n} sections)")
print(f"labels   : {len(labels)}")
print(f"bibitems : {len(keys)}   cited: {len(cites)}")

if warns:
    print("\nwarnings:")
    for w in warns:
        print(f"  ! {w}")
if errs:
    print("\nERRORS:")
    for e in errs:
        print(f"  x {e}")
    sys.exit(1)
print("\nstructural checks passed")
