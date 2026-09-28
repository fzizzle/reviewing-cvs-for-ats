import pathlib

import pytest

import cvlib
import layout
import repeats
import score

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "cv-template.html"
try:
    cvlib.find_chrome()
    HAVE_CHROME = True
except RuntimeError:
    HAVE_CHROME = False
needs_chrome = pytest.mark.skipif(not HAVE_CHROME, reason="needs Chrome/Chromium/Edge")


@needs_chrome
def test_template_parses_cleanly_in_every_parser():
    for name, r in score.score_cv(TEMPLATE).items():
        assert r["parse"] >= 62, (name, r)
        assert not r["garbled"] and not r["misplaced_dates"] and not r["missing_sections"], (name, r)


@needs_chrome
def test_template_layout(tmp_path):
    r = layout.check(cvlib.render_pdf(TEMPLATE, tmp_path / "t.pdf"), max_pages=1)
    assert r["problems"] == [], r


def test_template_has_no_repetition():
    bullets, text = repeats.load(TEMPLATE)
    assert repeats.repeated_openers(bullets) == {}
    assert repeats.repeated_phrases(text) == []


@needs_chrome
def test_dense_fixture_is_flagged():
    rows = score.score_cv(ROOT / "tests" / "fixtures" / "dense_cv.html")
    assert all(r["dates"] <= 5 for r in rows.values())            # years-only dates
    assert all("location" in r["missing_contact"] for r in rows.values())


SCANNED_HTML = ("<html><body><h2>Experience</h2><p>" + "Registered nurse on an acute medical ward. " * 12
                + "</p><h2>Education</h2><p>BSc Nursing</p><h2>Skills</h2><p>Triage</p></body></html>")


def _scanned_pdf(tmp_path):
    """A text PDF rasterised into an image-only PDF, like a scanned CV."""
    import pymupdf
    html = tmp_path / "cv.html"
    html.write_text(SCANNED_HTML, encoding="utf-8")
    src = pymupdf.open(cvlib.render_pdf(html, tmp_path / "text.pdf"))
    out = pymupdf.open()
    for page in src:
        pix = page.get_pixmap(dpi=100)
        out.new_page(width=page.rect.width, height=page.rect.height).insert_image(page.rect, pixmap=pix)
    path = tmp_path / "scanned.pdf"
    out.save(path)
    return path


@needs_chrome
def test_scanned_pdf_is_reported_not_crashed(tmp_path, capsys):
    pdf = _scanned_pdf(tmp_path)
    assert layout.main([str(pdf)]) == 2
    assert "cvats: error: no extractable text" in capsys.readouterr().err
    assert "no extractable text" in score.problems(score.score_cv(pdf))[0]
    assert repeats.main([str(pdf)]) == 2
    assert "cvats: error: no extractable text" in capsys.readouterr().err
