import pytest

import cvlib
from build_fixtures import W_NS, build_nurse_docx, build_word_template_docx


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


def test_extract_all_normalises_and_counts_ligatures(tmp_path):
    f = tmp_path / "cv.txt"
    f.write_text("Certi\ufb01ed o\ufb03ce", encoding="utf-8")
    texts, _ = cvlib.extract_all(f)
    assert texts == {"text": "Certified office"} and texts.ligatures == {"text": 2}


def test_unsupported_format(tmp_path):
    f = tmp_path / "cv.odt"
    f.write_text("x")
    with pytest.raises(ValueError, match="Unsupported"):
        cvlib.extract_all(f)


def test_docx_reads_content_controls(tmp_path):
    texts, _ = cvlib.extract_all(build_word_template_docx(tmp_path / "w.docx"))
    assert set(texts) == {"python-docx", "docx-xml"}
    for name, text in texts.items():
        assert "BTEC Level 3 Business" in text, name
        assert text.index("Education") < text.index("BTEC") < text.index("Skills"), name


def test_docx_text_boxes_only_in_lenient_parser(tmp_path):
    path = build_word_template_docx(tmp_path / "w.docx")
    texts, _ = cvlib.extract_all(path)
    assert "morgan.blake@example.com" not in texts["python-docx"]
    assert texts["docx-xml"].count("morgan.blake@example.com") == 1
    assert cvlib.docx_textbox_text(path) == "morgan.blake@example.com · +44 20 7946 0456"


def build_tabs_and_breaks_docx(out):
    """A .docx with a tab and a line break gluing words together if w:tab/w:br/w:cr are ignored,
    in the body and inside a text box."""
    import docx
    from docx.oxml import parse_xml
    d = docx.Document()
    p = d.add_paragraph()
    p.add_run("Job Title")
    p.add_run().add_tab()
    p.add_run("2020 - 2021")
    p2 = d.add_paragraph()
    p2.add_run("Before break")
    p2.add_run().add_break()
    p2.add_run("After break")
    d.add_paragraph()._p.append(parse_xml(
        f'<w:r xmlns:w="{W_NS}" xmlns:v="urn:schemas-microsoft-com:vml"><w:pict>'
        '<v:shape style="width:300pt;height:20pt"><v:textbox><w:txbxContent><w:p><w:r>'
        '<w:t>Left</w:t></w:r><w:r><w:tab/></w:r><w:r><w:t>Right</w:t></w:r></w:p>'
        '</w:txbxContent></v:textbox></v:shape></w:pict></w:r>'))
    d.save(out)
    return out


def test_docx_xml_text_keeps_tabs_and_breaks_apart(tmp_path):
    path = build_tabs_and_breaks_docx(tmp_path / "w.docx")
    text = cvlib.docx_xml_text(path)
    assert "Job Title\t2020 - 2021" in text
    assert "Before break\nAfter break" in text


def test_docx_textbox_text_keeps_tabs_apart(tmp_path):
    path = build_tabs_and_breaks_docx(tmp_path / "w.docx")
    assert cvlib.docx_textbox_text(path) == "Left Right"


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
