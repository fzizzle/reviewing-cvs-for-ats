import pytest

import cvlib
from build_fixtures import build_nurse_docx


def test_txt_extraction(tmp_path):
    f = tmp_path / "cv.txt"
    f.write_text("EXPERIENCE\nNurse\n", encoding="utf-8")
    texts, pages = cvlib.extract_all(f)
    assert texts == {"text": "EXPERIENCE\nNurse\n"} and pages is None


def test_docx_keeps_document_order(tmp_path):
    texts, pages = cvlib.extract_all(build_nurse_docx(tmp_path / "n.docx"))
    text = texts["python-docx"]
    assert pages is None
    assert text.index("2021 – Present") < text.index("Skills")  # table rows stay in place


def test_docx_header_text_is_reported(tmp_path):
    path = build_nurse_docx(tmp_path / "n.docx")
    assert "jordan.lee@example.com" in cvlib.docx_header_footer_text(path)
    assert "jordan.lee@example.com" not in cvlib.extract_all(path)[0]["python-docx"]


def test_unsupported_format(tmp_path):
    f = tmp_path / "cv.odt"
    f.write_text("x")
    with pytest.raises(ValueError, match="Unsupported"):
        cvlib.extract_all(f)


try:
    cvlib.find_chrome()
    HAVE_CHROME = True
except RuntimeError:
    HAVE_CHROME = False


@pytest.mark.skipif(not HAVE_CHROME, reason="needs Chrome/Chromium/Edge")
def test_html_renders_and_all_parsers_run(tmp_path):
    f = tmp_path / "cv.html"
    f.write_text("<html><body><h2>Experience</h2><p>Nurse, Jan 2020 – Present</p></body></html>", encoding="utf-8")
    texts, pages = cvlib.extract_all(f)
    assert pages == 1
    assert set(texts) == {"pypdf", "pdfminer", "pdfplumber", "pymupdf"}
    assert all("Nurse" in t for t in texts.values())


@pytest.mark.skipif(not HAVE_CHROME, reason="needs Chrome/Chromium/Edge")
def test_rerender_overwrites_stale_pdf(tmp_path):
    """render_pdf must not leave a PDF from a previous render at the same path.

    Regression for: an existing PDF at pdf_path made the stable-size poll see the old
    file as "done" almost immediately, killing Chrome before it wrote the new content.
    """
    html = tmp_path / "cv.html"
    pdf = tmp_path / "cv.pdf"
    html.write_text("<html><body><h1>Original Name</h1></body></html>", encoding="utf-8")
    cvlib.render_pdf(html, pdf)
    assert "Original Name" in cvlib.PDF_PARSERS["pypdf"](pdf)

    html.write_text("<html><body><h1>Changed Name</h1></body></html>", encoding="utf-8")
    cvlib.render_pdf(html, pdf)
    text = cvlib.PDF_PARSERS["pypdf"](pdf)
    assert "Changed Name" in text
    assert "Original Name" not in text
