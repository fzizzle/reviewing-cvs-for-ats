#!/usr/bin/env python3
"""Check a CV's printed layout from PDF word coordinates.

Reports page count, body font size (most common glyph size), smallest text, margins (mm),
how empty the last page is, and orphan lines: a wrapped bullet or paragraph whose last line
holds only 1-2 words, side-by-side columns, dates in a right-aligned column, and invisible
text (white, under 4pt or off-page). Input: .pdf, or .html (rendered with headless Chrome first).
Exit code 1 when a check fails.

Usage: cvats layout CV [--max-pages N] [--min-body-pt 9.5]
"""
import argparse
import collections
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from cvlib import NO_TEXT, as_pdf, cli  # noqa: E402

BULLET_GLYPHS = ("•", "▪", "‣", "◦", "-", "–", "*")
MM_PER_PT = 25.4 / 72


def page_lines(page):
    """Group a pdfplumber page's words into visual lines.

    Chrome renders <li> bullet glyphs as filled vector curves rather than text, so a line that
    starts a list item is flagged with marker=True when a curve sits just left of it. Each curve is
    assigned to exactly one line: the line to its right (curve x1 <= line x0) whose vertical centre
    is nearest the curve's vertical midpoint, within 6pt. At tight line spacing a wrapped
    continuation line can sit close enough that a naive top..bottom window would match it too, so
    picking the single nearest line (rather than marking every line whose window contains the
    curve) keeps the marker on the bullet's first line only.
    """
    words = sorted(page.extract_words(extra_attrs=["size"]), key=lambda w: (w["top"], w["x0"]))
    lines = []
    for w in words:
        if lines and abs(w["top"] - lines[-1]["top"]) <= 2:
            line = lines[-1]
            line["words"].append(w)
            line["x0"], line["x1"] = min(line["x0"], w["x0"]), max(line["x1"], w["x1"])
            line["bottom"] = max(line["bottom"], w["bottom"])
        else:
            lines.append({"top": w["top"], "bottom": w["bottom"], "x0": w["x0"], "x1": w["x1"],
                          "size": w["size"], "words": [w]})
    for line in lines:
        line["text"] = " ".join(w["text"] for w in sorted(line["words"], key=lambda w: w["x0"]))
    mark_nearest_line(lines, page.curves)
    return lines


def mark_nearest_line(lines, curves, max_dist=6):
    """Set marker=True on the single line nearest each curve's vertical midpoint (see page_lines)."""
    for curve in curves:
        cy = (curve["top"] + curve["bottom"]) / 2
        best, best_dist = None, None
        for line in lines:
            if curve["x1"] > line["x0"]:
                continue
            dist = abs((line["top"] + line["bottom"]) / 2 - cy)
            if dist <= max_dist and (best is None or dist < best_dist):
                best, best_dist = line, dist
        if best is not None:
            best["marker"] = True


def find_orphans(lines, right_edge, max_words=2, slack=40, gap_factor=1.55):
    """Short last lines of wrapped text: the line above ran to the right edge and this one continues it."""
    orphans = []
    for prev, cur in zip(lines, lines[1:]):
        gap = cur["top"] - prev["top"]
        wrapped = prev["x1"] >= right_edge - slack and 0 < gap <= prev["size"] * gap_factor
        continues = (cur["x0"] >= prev["x0"] - 1 and not cur["text"].startswith(BULLET_GLYPHS)
                     and not cur.get("marker"))
        if wrapped and continues and len(cur["text"].split()) <= max_words:
            orphans.append(f"…{prev['text'][-40:]} ⏎ {cur['text']}")
    return orphans


DATEISH = re.compile(r"(?:19|20)\d{2}|present|current|now|aujourd|heute|actual", re.I)


def find_gutter(lines, min_run=6, half_width=4, step=2):
    """The strongest vertical gutter on a page, or None.

    A gutter is an x position where, for min_run consecutive lines, no word crosses a band
    2*half_width wide, with text left of it on at least 3 of those lines and right of it on at
    least 3. Word spaces are narrower than the band, so single-column text never qualifies.
    Returns {"x", "lines", "right"}: right is the text right of the gutter, line by line.
    """
    if not lines:
        return None
    left, right = min(line["x0"] for line in lines), max(line["x1"] for line in lines)
    margin = 0.15 * (right - left)
    best, x = None, left + margin
    while x <= right - margin:
        run, lefts, rights = [], 0, 0
        for line in lines:
            if any(w["x0"] < x + half_width and w["x1"] > x - half_width for w in line["words"]):
                run, lefts, rights = [], 0, 0
                continue
            run.append(line)
            lefts += any(w["x1"] <= x for w in line["words"])
            rights += any(w["x0"] >= x for w in line["words"])
            if len(run) >= min_run and lefts >= 3 and rights >= 3 and (best is None or len(run) > best["lines"]):
                best = {"x": round(x), "lines": len(run), "run": list(run)}
        x += step
    if best is None:
        return None
    texts = (" ".join(w["text"] for w in line["words"] if w["x0"] >= best["x"]) for line in best.pop("run"))
    best["right"] = [t for t in texts if t]
    return best


def right_aligned_dates(lines, right_edge, min_gap_em=2.5, slack=15):
    """Dates pushed to the right edge, far from the rest of their line (flex, grid or tab alignment)."""
    found = []
    for line in lines:
        words = sorted(line["words"], key=lambda w: w["x0"])
        for a, b in zip(words, words[1:]):
            if b["x0"] - a["x1"] > min_gap_em * line["size"]:
                tail = " ".join(w["text"] for w in words if w["x0"] >= b["x0"])
                if DATEISH.search(tail) and line["x1"] >= right_edge - slack:
                    found.append(tail)
                break
    return found


def _is_white(color):
    if not isinstance(color, (list, tuple)):
        color = (color,)
    if not color or not all(isinstance(v, (int, float)) for v in color):
        return False  # pattern fills, unknown colour spaces
    return max(color) <= 0.05 if len(color) == 4 else min(color) >= 0.95  # CMYK, else grey/RGB


def invisible_words(page, min_pt=4):
    """Words a reader can't see but a parser still reads: white text with no dark shape behind it,
    text under min_pt, or text off the page."""
    fills = [s for s in page.rects + page.curves if s.get("fill") and not _is_white(s.get("non_stroking_color"))]
    out = []
    for w in page.extract_words(extra_attrs=["non_stroking_color", "size"]):
        off = w["x1"] < 0 or w["x0"] > page.width or w["bottom"] < 0 or w["top"] > page.height
        white = _is_white(w["non_stroking_color"]) and not any(
            s["x0"] <= w["x0"] and s["x1"] >= w["x1"] and s["top"] <= w["top"] and s["bottom"] >= w["bottom"]
            for s in fills)
        if off or white or w["size"] < min_pt:
            out.append(w["text"])
    return out


def pdf_findings(pdf_path):
    """ATS layout traps per page: side-by-side columns, right-aligned dates and invisible text."""
    import pdfplumber
    out = []
    with pdfplumber.open(str(pdf_path)) as doc:
        for n, page in enumerate(doc.pages, 1):
            lines = page_lines(page)
            if not lines:
                continue
            dates = right_aligned_dates(lines, max(line["x1"] for line in lines))
            if len(dates) >= 2:
                out.append(f"page {n}: {len(dates)} dates in a right-aligned column (e.g. {dates[0]!r}); some ATS "
                           "detach them from the job — put them inline after the employer")
            gutter = find_gutter(lines)
            if gutter and sum(bool(DATEISH.search(t)) for t in gutter["right"]) < 0.6 * len(gutter["right"]):
                out.append(f"page {n}: side-by-side columns over {gutter['lines']} lines (right column starts "
                           f"{gutter['right'][0][:40]!r}); ATS may read across both — use one column")
            hidden = invisible_words(page)
            if hidden:
                out.append(f"page {n}: {len(hidden)} invisible word(s) a parser still reads "
                           f"({' '.join(hidden[:6])!r}) — remove hidden text")
    return out


def check(pdf_path, max_pages=2, min_body_pt=9.5):
    import pdfplumber
    sizes, orphans = collections.Counter(), []
    with pdfplumber.open(str(pdf_path)) as doc:
        pages = len(doc.pages)
        boxes = []
        for page in doc.pages:
            sizes.update(round(ch["size"], 1) for ch in page.chars if ch["text"].strip())
            lines = page_lines(page)
            if lines:
                orphans += find_orphans(lines, max(line["x1"] for line in lines))
                boxes.append((min(l["x0"] for l in lines), max(l["x1"] for l in lines),
                              min(l["top"] for l in lines), page.height - max(l["bottom"] for l in lines),
                              page.height, page.width))
    if not boxes:
        raise ValueError(NO_TEXT)
    # Margins: left/right are the tightest indent seen on ANY page (a short page 1 must not look
    # like it has a wide margin just because its own lines didn't reach as far as later pages').
    left = min(b[0] for b in boxes)
    right = boxes[0][5] - max(b[1] for b in boxes)
    top = boxes[0][2]
    bottom, height = boxes[-1][3], boxes[-1][4]
    body = sizes.most_common(1)[0][0] if sizes else 0
    report = {
        "pages": pages, "body_pt": body, "min_pt": min(sizes) if sizes else 0,
        "margins_mm": {k: round(v * MM_PER_PT, 1) for k, v in
                       (("left", left), ("right", right), ("top", top), ("bottom", bottom))},
        "last_page_empty_pct": round(100 * bottom / height, 1), "orphans": orphans, "problems": [],
    }
    p = report["problems"]
    if pages > max_pages:
        p.append(f"{pages} pages (max {max_pages})")
    if body < min_body_pt:
        p.append(f"body text {body}pt is below {min_body_pt}pt (most CV guidance: 10–11pt)")
    if abs(report["margins_mm"]["left"] - report["margins_mm"]["right"]) > 3:
        p.append(f"left/right margins differ: {report['margins_mm']}")
    if pages == 1 and report["last_page_empty_pct"] > 20:
        p.append(f"page is {report['last_page_empty_pct']}% empty at the bottom: room for larger text or spacing")
    if orphans:
        p.append(f"{len(orphans)} orphan line(s)")
    p.extend(pdf_findings(pdf_path))
    return report


@cli
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cv")
    ap.add_argument("--max-pages", type=int, default=2)
    ap.add_argument("--min-body-pt", type=float, default=9.5)
    a = ap.parse_args(argv)
    with tempfile.TemporaryDirectory() as work:
        pdf = as_pdf(a.cv, work)
        if pdf is None:
            raise ValueError("layout needs a .pdf or .html CV")
        r = check(pdf, a.max_pages, a.min_body_pt)
    print(f"pages: {r['pages']}  body: {r['body_pt']}pt  smallest: {r['min_pt']}pt  margins(mm): {r['margins_mm']}")
    print(f"bottom of last page empty: {r['last_page_empty_pct']}%")
    for o in r["orphans"]:
        print("orphan:", o)
    print("problems:", "; ".join(r["problems"]) if r["problems"] else "none")
    return 1 if r["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
