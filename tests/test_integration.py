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
