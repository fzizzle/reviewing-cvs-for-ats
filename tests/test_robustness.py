"""Rendering never loses a file; one failing parser or a bad file gives a clear result, not a traceback."""
import pathlib

import pytest

import cvlib
import extract
import score

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
try:
    cvlib.find_chrome()
    HAVE_CHROME = True
except RuntimeError:
    HAVE_CHROME = False
needs_chrome = pytest.mark.skipif(not HAVE_CHROME, reason="needs Chrome/Chromium/Edge")


def test_render_refuses_to_overwrite_its_input(tmp_path):
    html = tmp_path / "cv.html"
    html.write_text("<p>Jane Example</p>", encoding="utf-8")
    with pytest.raises(ValueError, match="is the input file"):
        cvlib.render_pdf(html, html)
    assert html.read_text(encoding="utf-8") == "<p>Jane Example</p>"


def test_failed_render_keeps_the_previous_pdf(tmp_path, monkeypatch):
    html, pdf = tmp_path / "cv.html", tmp_path / "cv.pdf"
    html.write_text("<p>Jane Example</p>", encoding="utf-8")
    pdf.write_bytes(b"%PDF-1.4 previous version")
    monkeypatch.setattr(cvlib, "find_chrome", lambda: "/nonexistent/chrome")
    with pytest.raises(OSError):
        cvlib.render_pdf(html, pdf)
    assert pdf.read_bytes() == b"%PDF-1.4 previous version"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["cv.html", "cv.pdf"]


@needs_chrome
def test_render_replaces_an_existing_pdf(tmp_path):
    html, pdf = tmp_path / "cv.html", tmp_path / "cv.pdf"
    html.write_text("<p>Jane Example</p>", encoding="utf-8")
    pdf.write_bytes(b"%PDF-1.4 stale")
    cvlib.render_pdf(html, pdf)
    assert pdf.read_bytes()[:5] == b"%PDF-" and pdf.stat().st_size > 100
    assert sorted(p.name for p in tmp_path.iterdir()) == ["cv.html", "cv.pdf"]


def _broken(path):
    raise KeyError("bad xref table")


@needs_chrome
def test_one_failing_pdf_parser_keeps_the_others(monkeypatch):
    monkeypatch.setitem(cvlib.PDF_PARSERS, "pypdf", _broken)
    texts, _ = cvlib.extract_all(ROOT / "templates" / "cv-template.html")
    assert "pypdf" not in texts and len(texts) == 3
    assert "bad xref table" in texts.parser_errors["pypdf"]
    rows = score.score_cv(ROOT / "templates" / "cv-template.html")
    assert any("pypdf could not read the file" in line for line in score.problems(rows))


def test_every_parser_failing_is_bad_input(monkeypatch):
    monkeypatch.setitem(cvlib.PDF_PARSERS, "pypdf", _broken)
    with pytest.raises(ValueError, match="any parser"):
        cvlib._run_parsers({"pypdf": _broken}, "x.pdf")


def test_missing_and_corrupt_files_exit_2(tmp_path, capsys):
    corrupt = tmp_path / "cv.docx"
    corrupt.write_bytes(b"not a zip file")
    assert extract.main([str(tmp_path / "missing.docx")]) == 2
    assert extract.main([str(corrupt)]) == 2
    err = capsys.readouterr().err
    assert "No such file" in err and "Could not read cv.docx" in err
