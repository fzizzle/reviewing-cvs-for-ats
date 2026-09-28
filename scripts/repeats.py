#!/usr/bin/env python3
"""Find repetition in a CV.

Reports (1) bullets that open with the same word (label prefixes such as "Forecasting:" are skipped),
(2) 3-word content phrases used more than once, (3) --terms used more than once.
Bullets: <li> in .html; list paragraphs in .docx; lines starting with •, -, *, ▪ in .pdf/.txt/.md.
Exit code 1 when anything repeats.

Usage: cvats repeats CV [--terms "Acme,Oxford,SAMPE"] [--allow "python,sql"]
"""
import argparse
import collections
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from cvlib import PDF_PARSERS  # noqa: E402

MONTHS = ("jan feb mar apr may jun jul aug sep sept oct nov dec january february march april june july "
          "august september october november december present current janv févr fevr mars avr mai juin "
          "juil août aout déc janvier février avril juillet septembre octobre novembre décembre")
STOP = set(("a an the and or of to in on at by for with from as into across via per is are was were be been "
            "it its this that these those their his her our your my i we you he she they plus while than then "
            "also over under up out " + MONTHS).split())
BULLET = re.compile(r"^\s*[•▪‣◦*\-–]\s+")
LABEL = re.compile(r"^\s*([^:]{1,60}):\s+(.*)$")
WORD = re.compile(r"[a-zà-ÿ0-9+#][a-zà-ÿ0-9+#'’-]*")


class _Html(HTMLParser):
    BLOCK = {"p", "div", "li", "h1", "h2", "h3", "h4", "ul", "ol", "br", "section", "header", "tr"}

    def __init__(self):
        super().__init__()
        self.skip, self.li, self.bullets, self._buf, self.chunks = 0, 0, [], [], []

    def handle_starttag(self, tag, attrs):
        if tag in ("head", "style", "script"):
            self.skip += 1
        if tag == "li":
            self.li += 1
            self._buf = []
        if tag in self.BLOCK:
            self.chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in ("head", "style", "script"):
            self.skip -= 1
        if tag == "li" and self.li:
            self.li -= 1
            self.bullets.append(" ".join("".join(self._buf).split()))
        if tag in self.BLOCK:
            self.chunks.append("\n")

    def handle_data(self, data):
        if self.skip:
            return
        self.chunks.append(data)
        if self.li:
            self._buf.append(data)


def load(path):
    """Return (bullets, full text) for a .html, .docx, .pdf, .txt or .md CV."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext in (".html", ".htm"):
        h = _Html()
        h.feed(p.read_text(encoding="utf-8"))
        return h.bullets, "".join(h.chunks)
    if ext == ".docx":
        import docx
        d = docx.Document(str(p))
        bullets = [para.text for para in d.paragraphs if "List" in para.style.name and para.text.strip()]
        return bullets, "\n".join(para.text for para in d.paragraphs)
    if ext == ".pdf":
        # Chrome renders <li> markers as filled vector curves, not the bullet glyphs a text-only
        # scan looks for, so a PDF made from an <ul>/<li> CV would otherwise show zero bullets.
        # Reuse layout.page_lines(), which already flags such lines via marker=True.
        import pdfplumber
        import layout  # local import: avoids a circular import (layout.py doesn't import repeats)
        bullets = []
        with pdfplumber.open(str(p)) as doc:
            for page in doc.pages:
                for line in layout.page_lines(page):
                    if BULLET.match(line["text"]) or line.get("marker"):
                        bullets.append(BULLET.sub("", line["text"]))
        return bullets, PDF_PARSERS["pdfplumber"](str(p))
    text = p.read_text(encoding="utf-8")
    return [BULLET.sub("", line) for line in text.splitlines() if BULLET.match(line)], text


def opener(bullet):
    m = LABEL.match(bullet)
    if m and len(m.group(1).split()) <= 6:
        bullet = m.group(2)
    words = WORD.findall(bullet.lower())
    return words[0] if words else ""


def repeated_openers(bullets):
    counts = collections.Counter(opener(b) for b in bullets)
    return {w: c for w, c in counts.items() if w and c > 1}


def repeated_phrases(text, n=3, allow=()):
    words = [w for w in WORD.findall(text.lower()) if w not in STOP and not w.isdigit()]
    grams = collections.Counter(zip(*(words[i:] for i in range(n))))
    allowed = {a.lower() for a in allow}
    return sorted(" ".join(g) for g, c in grams.items() if c > 1 and not set(g) <= allowed)


def term_counts(text, terms):
    return {t: len(re.findall(r"(?<!\w)" + re.escape(t) + r"(?!\w)", text, re.I)) for t in terms}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cv")
    ap.add_argument("--terms", default="", help="comma-separated names that should appear once")
    ap.add_argument("--allow", default="", help="comma-separated words allowed to repeat (e.g. skills)")
    a = ap.parse_args(argv)
    bullets, text = load(a.cv)
    if Path(a.cv).suffix.lower() == ".pdf" and not bullets:
        print("warning: no bullets detected in this PDF — run repeats on the source .html/.docx to check bullet openers")
    openers = repeated_openers(bullets)
    phrases = repeated_phrases(text, allow=[w for w in a.allow.split(",") if w])
    terms = {t: c for t, c in term_counts(text, [t.strip() for t in a.terms.split(",") if t.strip()]).items() if c > 1}
    print(f"bullets checked: {len(bullets)}")
    print("repeated bullet openers:", openers or "none")
    print("repeated 3-word phrases:", phrases or "none")
    print("terms used more than once:", terms or "none")
    return 1 if openers or phrases or terms else 0


if __name__ == "__main__":
    sys.exit(main())
