"""Shared helpers for the CV ATS toolkit: find Chrome, render HTML to PDF, extract text with several parsers."""
import functools
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

logging.getLogger("pdfminer").setLevel(logging.ERROR)

NO_TEXT = "no extractable text (scanned image?) — an ATS sees an empty CV; rebuild as a text PDF"
MIN_WORDS = 30  # fewer words than this and the CV has, in effect, no text


def cli(main):
    """Wrap a script's main(): report bad input as "cvats: error: ..." on stderr and return 2."""
    @functools.wraps(main)
    def wrapper(argv=None):
        try:
            return main(argv)
        except (RuntimeError, ValueError, OSError) as err:
            print(f"cvats: error: {err}", file=sys.stderr)
            return 2
    return wrapper

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge",
]


def find_chrome():
    """Return a Chrome/Chromium/Edge binary. CV_ATS_CHROME overrides the search."""
    if os.environ.get("CV_ATS_CHROME"):
        return os.environ["CV_ATS_CHROME"]
    for cand in CHROME_CANDIDATES:
        path = cand if os.path.isabs(cand) else shutil.which(cand)
        if path and os.path.exists(path):
            return path
    raise RuntimeError("No Chrome, Chromium or Edge found. Install one or set CV_ATS_CHROME.")


def render_pdf(html_path, pdf_path, timeout=120):
    """Print an HTML file to PDF with headless Chrome, using a throwaway browser profile.

    On this machine, Chrome 154 hangs after --print-to-pdf finishes specifically when pointed at a
    fresh, empty --user-data-dir: confirmed by running it three ways with a temporary profile (bare,
    plus --no-first-run --no-default-browser-check, and with a pre-seeded "First Run" sentinel file)
    and getting a hang each time, versus exiting on its own in 0.57s with no --user-data-dir at all.
    So this isn't "modern Chrome" hanging in general, and the first-run flags don't dodge it either
    -- it's the throwaway profile specifically (which we still need, to avoid touching the user's
    real Chrome profile) that triggers it. So rather than subprocess.run(..., timeout=...) waiting
    for the process to exit, we poll for the PDF's size to stop changing and then terminate the
    browser ourselves. This relies on Chrome writing the PDF in a single burst rather than
    incrementally; the reviewer observed that hold even for a 280-page PDF.
    """
    html_path, pdf_path = Path(html_path).resolve(), Path(pdf_path).resolve()
    pdf_path.unlink(missing_ok=True)  # a stale PDF here makes the stable-size poll below
    # see the old file as "done" almost immediately, killing Chrome before it writes.
    with tempfile.TemporaryDirectory() as profile:
        proc = subprocess.Popen(
            [find_chrome(), "--headless", "--disable-gpu", "--no-pdf-header-footer",
             f"--user-data-dir={profile}", f"--print-to-pdf={pdf_path}", html_path.as_uri()],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + timeout
        last_size, stable = -1, 0
        while time.monotonic() < deadline and proc.poll() is None:
            if pdf_path.exists():
                size = pdf_path.stat().st_size
                if size > 0 and size == last_size:
                    stable += 1
                    if stable >= 2:
                        break
                else:
                    stable = 0
                last_size = size
            time.sleep(0.1)
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
    if not pdf_path.exists():
        raise RuntimeError(f"Chrome did not write {pdf_path}")
    return pdf_path


def _pypdf(p):
    import pypdf
    return "\n".join(pg.extract_text() or "" for pg in pypdf.PdfReader(p).pages)


def _pdfminer(p):
    from pdfminer.high_level import extract_text
    return extract_text(p)


def _pdfplumber(p):
    import pdfplumber
    with pdfplumber.open(p) as doc:
        return "\n".join(pg.extract_text() or "" for pg in doc.pages)


def _pymupdf(p):
    import pymupdf
    with pymupdf.open(p) as doc:
        return "\n".join(pg.get_text() for pg in doc)


PDF_PARSERS = {"pypdf": _pypdf, "pdfminer": _pdfminer, "pdfplumber": _pdfplumber, "pymupdf": _pymupdf}


def docx_text(path):
    """Body text of a .docx in document order: paragraphs, table rows (one line per row) and content
    controls (w:sdt, used by Word's CV templates). Text boxes are left out, as many ATS leave them out."""
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    d = docx.Document(str(path))
    parts = []

    def walk(parent):
        for child in parent.iterchildren():
            tag = child.tag.rsplit("}", 1)[-1]
            if tag == "p":
                parts.append(Paragraph(child, d).text)
            elif tag == "tbl":
                for row in Table(child, d).rows:
                    parts.append(" ".join(cell.text for cell in row.cells))
            elif tag in ("sdt", "sdtContent"):
                walk(child)

    walk(d.element.body)
    return "\n".join(parts)


MC_FALLBACK = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"


RUN_MARKS = {"tab": "\t", "br": "\n", "cr": "\n"}  # w:tab/w:br/w:cr rendered as their text equivalent


def docx_xml_text(path):
    """Every paragraph's own text in XML order, text boxes included: what a lenient ATS reads."""
    import docx
    from docx.oxml.ns import qn
    d = docx.Document(str(path))
    tags = [qn(f"w:{t}") for t in ("t", "tab", "br", "cr")]
    lines = []
    for p in d.element.body.iter(qn("w:p")):
        if any(a.tag == MC_FALLBACK for a in p.iterancestors()):
            continue  # Word stores each text box twice; the Fallback copy is the duplicate
        lines.append("".join(
            RUN_MARKS.get(el.tag.rsplit("}", 1)[-1], el.text or "") for el in p.iter(*tags)
            if next(el.iterancestors(qn("w:p"))) is p))
    return "\n".join(lines)


def docx_textbox_text(path):
    """Text inside Word text boxes and shapes. Many ATS skip it, so details there get lost."""
    import docx
    from docx.oxml.ns import qn
    d = docx.Document(str(path))
    tags = [qn(f"w:{t}") for t in ("t", "tab", "br", "cr")]
    t_tag = qn("w:t")
    boxes = []
    for box in d.element.body.iter(qn("w:txbxContent")):
        text = " ".join("".join((el.text or "") if el.tag == t_tag else " " for el in p.iter(*tags))
                        for p in box.iter(qn("w:p")))
        if text.strip():
            boxes.append(" ".join(text.split()))
    return "\n".join(dict.fromkeys(boxes))  # de-duplicate Word's Choice/Fallback copies


def docx_header_footer_text(path):
    """Text in Word headers/footers. Many ATS skip it, so contact details there get lost."""
    import docx
    d = docx.Document(str(path))
    parts = []
    for section in d.sections:
        for part in (section.header, section.footer):
            parts.extend(p.text for p in part.paragraphs if p.text.strip())
    return "\n".join(parts)


def page_count(pdf_path):
    import pypdf
    return len(pypdf.PdfReader(str(pdf_path)).pages)


def as_pdf(path, workdir):
    """Return a PDF for a .pdf or .html CV (rendering HTML into workdir), else None."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".pdf":
        return path
    if ext in (".html", ".htm"):
        return render_pdf(path, Path(workdir) / (path.stem + ".pdf"))
    return None


LIGATURES = re.compile("[\ufb00-\ufb06]")  # ff, fi, fl, ffi, ffl, long-st, st ligature glyphs


class Extracted(dict):
    """{parser: text}, plus .ligatures = {parser: ligature glyphs found before normalising} and
    .pdf_findings = what extract_all's pdf_hook returned for the rendered PDF ([] without one)."""
    ligatures = {}
    pdf_findings = []


def normalise(texts):
    """NFKC-normalise each parser's text (U+FB01 -> "fi"), counting ligature glyphs first.

    An ATS that keeps the glyph misses words such as "Profile" or "certified", so the count is
    reported as a problem; normalising lets the other checks still score the words. Safe to call twice.
    """
    out = Extracted({n: unicodedata.normalize("NFKC", t) for n, t in texts.items()})
    prior = getattr(texts, "ligatures", {})
    out.ligatures = {n: prior.get(n, 0) + len(LIGATURES.findall(t)) for n, t in texts.items()}
    out.pdf_findings = getattr(texts, "pdf_findings", [])
    return out


def extract_all(path, pdf_hook=None):
    """Return ({parser: text}, page count or None) for a .pdf, .html, .docx, .txt or .md CV.

    Texts are NFKC-normalised; the returned dict's .ligatures holds each parser's ligature count.
    pdf_hook(pdf_path), if given, runs while the PDF exists; its result is kept in .pdf_findings.
    """
    path = Path(path)
    ext = path.suffix.lower()
    if ext not in (".pdf", ".html", ".htm", ".docx", ".txt", ".md"):
        raise ValueError(f"Unsupported CV format '{ext}'. Use .pdf, .html, .docx, .txt or .md "
                         "(save pasted text as .txt).")
    with tempfile.TemporaryDirectory() as work:
        pdf = as_pdf(path, work)
        if pdf is not None:
            texts = normalise({name: fn(str(pdf)) for name, fn in PDF_PARSERS.items()})
            texts.pdf_findings = pdf_hook(pdf) if pdf_hook else []
            return texts, page_count(pdf)
    if ext == ".docx":
        return normalise({"python-docx": docx_text(path), "docx-xml": docx_xml_text(path)}), None
    return normalise({"text": path.read_text(encoding="utf-8")}), None
