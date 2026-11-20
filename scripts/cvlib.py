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


# A CV holds personal data, so rendering must never touch the network or run the page's scripts.
# Every http(s)/ws request goes to a dead proxy; "<-loopback>" removes Chrome's built-in proxy
# bypass for localhost/127.0.0.1, and the resolver rule fails any DNS lookup that slips through.
# The remaining flags stop Chrome's own background traffic (updates, metrics, safe browsing).
# Scripts are blocked by the CSP that offline_copy() injects (--blink-settings=scriptEnabled=false
# stops headless Chrome printing at all).
# tests/test_offline_render.py checks this against a local request recorder.
OFFLINE_FLAGS = (
    "--proxy-server=http://127.0.0.1:9", "--proxy-bypass-list=<-loopback>",
    "--host-resolver-rules=MAP * ~NOTFOUND",
    "--disable-background-networking", "--disable-component-update", "--disable-sync",
    "--disable-domain-reliability", "--disable-client-side-phishing-detection",
    "--no-pings", "--metrics-recording-only", "--disable-features=MediaRouter,OptimizationHints",
)


# Second layer, inside the page: no scripts, and styles/images/fonts only from local files or inline.
CSP = ("default-src 'none'; script-src 'none'; connect-src 'none'; style-src 'unsafe-inline' file:; "
       "img-src file: data:; font-src file: data:; media-src 'none'; object-src 'none'; frame-src 'none'")


def offline_copy(html_path, workdir):
    """Copy of html_path with the CSP above as the first thing in <head>, plus a <base> so relative
    images and stylesheets still resolve against the original folder."""
    src = Path(html_path).read_text(encoding="utf-8", errors="replace")
    inject = (f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'
              f'<base href="{Path(html_path).parent.as_uri()}/">')
    m = re.search(r"<head\b[^>]*>", src, re.I)
    out = src[:m.end()] + inject + src[m.end():] if m else inject + src
    dest = Path(workdir) / "offline.html"
    dest.write_text(out, encoding="utf-8")
    return dest


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
    html_path, dest = Path(html_path).resolve(), Path(pdf_path).resolve()
    if dest == html_path:
        raise ValueError(f"Output {dest} is the input file; choose a different PDF path.")
    if not html_path.is_file():
        raise ValueError(f"No such file: {html_path}")
    # Chrome writes to a fresh temporary file beside the destination; the destination is only
    # replaced once that file is a complete PDF, so a failed render never loses an existing PDF.
    # (A fresh path also keeps the stable-size poll below from mistaking an old PDF for "done".)
    pdf_path = dest.with_name(f".{dest.stem}.{os.getpid()}.rendering.pdf")
    pdf_path.unlink(missing_ok=True)
    try:
        _render_to(html_path, pdf_path, timeout)
        with open(pdf_path, "rb") as fh:
            if fh.read(5) != b"%PDF-":
                raise RuntimeError(f"Chrome wrote something that is not a PDF for {html_path}")
        os.replace(pdf_path, dest)
    finally:
        pdf_path.unlink(missing_ok=True)
    return dest


def _render_to(html_path, pdf_path, timeout):
    with tempfile.TemporaryDirectory() as profile:
        page = offline_copy(html_path, profile)
        proc = subprocess.Popen(
            [find_chrome(), "--headless", "--disable-gpu", "--no-pdf-header-footer",
             f"--user-data-dir={profile}", *OFFLINE_FLAGS,
             f"--print-to-pdf={pdf_path}", page.as_uri()],
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
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        raise RuntimeError(f"Chrome did not write a PDF for {html_path}")


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
    .pdf_findings = what extract_all's pdf_hook returned for the rendered PDF ([] without one).
    .parser_errors = {parser: message} for parsers that failed on this file ({} if none)."""
    ligatures = {}
    pdf_findings = []
    parser_errors = {}


def normalise(texts):
    """NFKC-normalise each parser's text (U+FB01 -> "fi"), counting ligature glyphs first.

    An ATS that keeps the glyph misses words such as "Profile" or "certified", so the count is
    reported as a problem; normalising lets the other checks still score the words. Safe to call twice.
    """
    out = Extracted({n: unicodedata.normalize("NFKC", t) for n, t in texts.items()})
    prior = getattr(texts, "ligatures", {})
    out.ligatures = {n: prior.get(n, 0) + len(LIGATURES.findall(t)) for n, t in texts.items()}
    out.pdf_findings = getattr(texts, "pdf_findings", [])
    out.parser_errors = dict(getattr(texts, "parser_errors", {}))
    return out


def _run_parsers(parsers, path):
    """Run each parser on path; one failing parser must not hide what the others extracted.
    Failures go in .parser_errors; only if every parser fails is the file treated as unreadable."""
    texts, errors = Extracted(), {}
    for name, fn in parsers.items():
        try:
            texts[name] = fn(str(path))
        except Exception as err:  # noqa: BLE001 - parser libraries raise their own exception types
            errors[name] = f"{type(err).__name__}: {err}".strip()
    if not texts:
        detail = "; ".join(f"{n}: {e}" for n, e in errors.items())
        raise ValueError(f"Could not read {Path(path).name} with any parser ({detail})")
    texts.parser_errors = errors
    return texts


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
    if not path.is_file():
        raise ValueError(f"No such file: {path}")
    with tempfile.TemporaryDirectory() as work:
        pdf = as_pdf(path, work)
        if pdf is not None:
            texts = normalise(_run_parsers(PDF_PARSERS, pdf))
            texts.pdf_findings = pdf_hook(pdf) if pdf_hook else []
            return texts, page_count(pdf)
    if ext == ".docx":
        return normalise(_run_parsers({"python-docx": docx_text, "docx-xml": docx_xml_text}, path)), None
    return normalise({"text": path.read_text(encoding="utf-8")}), None
