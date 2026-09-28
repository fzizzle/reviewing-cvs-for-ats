"""Every cvats command reports bad input as 'cvats: error: …' on stderr and exits 2, never a traceback."""
import pytest

import extract
import layout
import render
import repeats
import score


@pytest.mark.parametrize("mod", [score, extract])
def test_unsupported_format_is_a_clean_error(mod, tmp_path, capsys):
    f = tmp_path / "cv.odt"
    f.write_text("x", encoding="utf-8")
    assert mod.main([str(f)]) == 2
    assert capsys.readouterr().err.startswith("cvats: error: Unsupported CV format")


def test_layout_rejects_docx_cleanly(tmp_path, capsys):
    f = tmp_path / "cv.docx"
    f.write_text("x", encoding="utf-8")
    assert layout.main([str(f)]) == 2
    assert capsys.readouterr().err.startswith("cvats: error:")


def test_render_reports_missing_browser(monkeypatch, tmp_path, capsys):
    def no_chrome(*a, **k):
        raise RuntimeError("No Chrome, Chromium or Edge found.")
    monkeypatch.setattr(render, "render_pdf", no_chrome)
    assert render.main([str(tmp_path / "cv.html")]) == 2
    assert capsys.readouterr().err.startswith("cvats: error: No Chrome")


def test_score_reports_bad_keyword_json(tmp_path, capsys):
    cv = tmp_path / "cv.txt"
    cv.write_text("EXPERIENCE\nNurse\n", encoding="utf-8")
    kw = tmp_path / "kw.json"
    kw.write_text("{not json", encoding="utf-8")
    assert score.main([str(cv), "--keywords", str(kw)]) == 2
    assert capsys.readouterr().err.startswith("cvats: error:")


def test_repeats_refuses_near_empty_text(tmp_path, capsys):
    f = tmp_path / "cv.txt"
    f.write_text("• Led x\n• Led y\n", encoding="utf-8")
    assert repeats.main([str(f)]) == 2
    assert "cvats: error: no extractable text" in capsys.readouterr().err


def test_score_problems_lead_with_empty_text():
    rows = {"a": score.score_text("", 1), "b": score.score_text("", 1)}
    assert "no extractable text (scanned image?)" in score.problems(rows)[0]
