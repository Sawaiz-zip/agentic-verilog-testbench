#!/usr/bin/env python3
"""
Render a .pptx to SVG/PNG by reading its packed XML, for visual QA.

Two routes:

  --powerpoint   the real thing. Drives PowerPoint over AppleScript to export a
                 PDF, then rasterises it. Needs Automation permission for the
                 app that owns this terminal (System Settings > Privacy &
                 Security > Automation). Note PowerPoint's sandbox refuses /tmp
                 and wants an HFS-style path, which this handles.

  (default)      a fallback that reads the packed XML and draws the geometry the
                 deck actually contains. Useful when PowerPoint is unavailable:
                 it catches overlapping shapes, text outside its box,
                 misalignment and elements off the slide. Fonts are
                 approximated, so judge geometry from it, not typography.

    python scripts/preview_deck.py docs/presentation.pptx --powerpoint
    python scripts/preview_deck.py docs/presentation.pptx --slides 4-8
"""

import argparse
import html
import pathlib
import re
import subprocess
import sys
import zipfile
from xml.dom import minidom

EMU = 914400.0
SCALE = 96.0          # px per inch in the preview
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def child(node, name):
    for c in node.childNodes:
        if c.nodeType == c.ELEMENT_NODE and c.tagName.endswith(":" + name):
            return c
    return None


def descend(node, *names):
    cur = node
    for n in names:
        cur = child(cur, n) if cur is not None else None
    return cur


def geom(sp):
    xfrm = descend(sp, "spPr", "xfrm") or descend(sp, "grpSpPr", "xfrm")
    if xfrm is None:
        return None
    off, ext = child(xfrm, "off"), child(xfrm, "ext")
    if off is None or ext is None:
        return None
    return (int(off.getAttribute("x")) / EMU, int(off.getAttribute("y")) / EMU,
            int(ext.getAttribute("cx")) / EMU, int(ext.getAttribute("cy")) / EMU)


def fill_of(sp):
    sf = descend(sp, "spPr", "solidFill")
    if sf is None:
        return None
    c = child(sf, "srgbClr")
    return "#" + c.getAttribute("val") if c is not None else None


def runs_of(sp):
    """[(text, size_pt, bold, colour)] flattened per paragraph."""
    tx = child(sp, "txBody")
    if tx is None:
        return []
    paras = []
    for p in tx.getElementsByTagName("a:p"):
        out = []
        for r in p.getElementsByTagName("a:r"):
            rpr = child(r, "rPr")
            size = int(rpr.getAttribute("sz")) / 100.0 if (rpr and rpr.getAttribute("sz")) else 18.0
            bold = bool(rpr and rpr.getAttribute("b") == "1")
            col = None
            if rpr is not None:
                sf = child(rpr, "solidFill")
                if sf is not None:
                    c = child(sf, "srgbClr")
                    if c is not None:
                        col = "#" + c.getAttribute("val")
            t = child(r, "t")
            txt = t.firstChild.nodeValue if (t is not None and t.firstChild) else ""
            if txt:
                out.append((txt, size, bold, col or "#222222"))
        paras.append(out)
    return paras


def wrap(text, size, width_in):
    """Greedy wrap at an approximate advance width of 0.50 em."""
    cpl = max(int((width_in * 72) / (size * 0.50)), 4)
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if len(trial) <= cpl:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def render(z, slide_name, media, w_in, h_in, rels):
    doc = minidom.parseString(z.read(slide_name))
    W, H = w_in * SCALE, h_in * SCALE
    body = []

    bg = doc.getElementsByTagName("p:bg")
    bgcol = "#ffffff"
    if bg:
        c = bg[0].getElementsByTagName("a:srgbClr")
        if c:
            bgcol = "#" + c[0].getAttribute("val")
    body.append(f'<rect width="{W}" height="{H}" fill="{bgcol}"/>')

    tree = doc.getElementsByTagName("p:cSld")[0]
    for sp in tree.getElementsByTagName("p:pic") + tree.getElementsByTagName("p:sp"):
        g = geom(sp)
        if not g:
            continue
        x, y, w, h = [v * SCALE for v in g]

        if sp.tagName.endswith("pic"):
            blip = sp.getElementsByTagName("a:blip")
            src = None
            if blip:
                rid = blip[0].getAttribute("r:embed")
                src = rels.get(rid)
            body.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
                        f'fill="#e9e9e6" stroke="#b9b9b3" stroke-width="1"/>')
            label = (src or "image").split("/")[-1]
            body.append(f'<text x="{x + w/2:.1f}" y="{y + h/2:.1f}" font-size="13" '
                        f'fill="#6a6a64" text-anchor="middle" font-family="Helvetica">'
                        f'[{html.escape(label)}]</text>')
            continue

        f = fill_of(sp)
        if f:
            body.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
                        f'rx="5" fill="{f}"/>')

        paras = runs_of(sp)
        if not any(paras):
            continue
        # text boxes get a faint outline so overflow is visible
        body.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
                    f'fill="none" stroke="#ff3b30" stroke-width="0.6" '
                    f'stroke-dasharray="3 3" opacity="0.30"/>')
        cy = y
        for para in paras:
            if not para:
                cy += 10
                continue
            size = para[0][1]
            colour = para[0][3]
            bold = para[0][2]
            text = "".join(t for t, _, _, _ in para)
            for line in wrap(text, size, g[2] - 0.08):
                cy += size * 1.25 * SCALE / 72
                wt = ' font-weight="700"' if bold else ''
                body.append(
                    f'<text x="{x + 4:.1f}" y="{cy:.1f}" font-size="{size * SCALE / 72:.1f}" '
                    f'fill="{colour}" font-family="Helvetica"{wt}>'
                    f'{html.escape(line)}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" '
            f'viewBox="0 0 {W:.0f} {H:.0f}">\n' + "\n".join(body) + "\n</svg>\n")


def via_powerpoint(deck: pathlib.Path, out: pathlib.Path) -> int:
    """Export through PowerPoint itself, then rasterise. The real render."""
    pdf = deck.parent / "_qa_deck.pdf"
    script = f'''
tell application "Microsoft PowerPoint"
  repeat while (count of presentations) > 0
    close presentation 1 saving no
  end repeat
  open POSIX file "{deck}"
  save presentation 1 in ((POSIX file "{pdf}") as string) as save as PDF
  return (count of slides of presentation 1)
end tell'''
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode != 0:
        msg = r.stderr.strip()
        print(f"PowerPoint export failed: {msg}", file=sys.stderr)
        if "-1743" in msg:
            print("Grant Automation permission to the app that owns this terminal:\n"
                  "  System Settings > Privacy & Security > Automation > "
                  "<your terminal or IDE> > Microsoft PowerPoint", file=sys.stderr)
        return 1
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("slide-*"):
        old.unlink()
    subprocess.run(["pdftoppm", "-jpeg", "-r", "100", str(pdf), str(out / "slide")],
                   check=True)
    pdf.unlink(missing_ok=True)
    shots = sorted(out.glob("slide-*.jpg"))
    print(f"{r.stdout.strip()} slides rendered via PowerPoint -> {out}")
    for s in shots:
        print(" ", s)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("deck")
    ap.add_argument("--out", default="/tmp/deckpreview")
    ap.add_argument("--slides", default=None, help="e.g. 4-8 or 12")
    ap.add_argument("--powerpoint", action="store_true",
                    help="render via PowerPoint instead of the XML fallback")
    args = ap.parse_args()

    if args.powerpoint:
        return via_powerpoint(pathlib.Path(args.deck).resolve(), pathlib.Path(args.out))

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("slide-*"):
        old.unlink()

    z = zipfile.ZipFile(args.deck)
    pres = minidom.parseString(z.read("ppt/presentation.xml"))
    sz = pres.getElementsByTagName("p:sldSz")[0]
    w_in = int(sz.getAttribute("cx")) / EMU
    h_in = int(sz.getAttribute("cy")) / EMU

    names = sorted([n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)],
                   key=lambda n: int(re.search(r"\d+", n.split("/")[-1]).group()))
    wanted = None
    if args.slides:
        if "-" in args.slides:
            a, b = args.slides.split("-")
            wanted = set(range(int(a), int(b) + 1))
        else:
            wanted = {int(args.slides)}

    made = []
    for i, n in enumerate(names, 1):
        if wanted and i not in wanted:
            continue
        relp = f"ppt/slides/_rels/{n.split('/')[-1]}.rels"
        rels = {}
        if relp in z.namelist():
            rd = minidom.parseString(z.read(relp))
            for r in rd.getElementsByTagName("Relationship"):
                rels[r.getAttribute("Id")] = r.getAttribute("Target")
        svg = render(z, n, None, w_in, h_in, rels)
        sp = out / f"slide-{i:02d}.svg"
        sp.write_text(svg)
        png = sp.with_suffix(".png")
        try:
            subprocess.run(["rsvg-convert", "-o", str(png), str(sp)], check=True)
            made.append(png)
        except Exception as e:
            print(f"  !! {sp.name}: {e}", file=sys.stderr)

    print(f"{len(made)} slides -> {out}")
    for m in made:
        print(" ", m)


if __name__ == "__main__":
    main()
