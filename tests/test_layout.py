import pytest

import cvlib
import layout


def L(top, x0, x1, text, size=9.0):
    return {"top": top, "x0": x0, "x1": x1, "text": text, "size": size}


FULL = "• Built contribution pages and pricing feeds for clients in London, Switzerland and"


def test_short_wrapped_last_line_is_an_orphan():
    out = layout.find_orphans([L(100, 50, 540, FULL), L(112.5, 58, 140, "Emerging Markets.")], right_edge=545)
    assert len(out) == 1 and "Emerging Markets." in out[0]


def test_next_bullet_is_not_an_orphan():
    assert layout.find_orphans([L(100, 50, 540, FULL), L(112.5, 50, 120, "• Led x")], right_edge=545) == []


def test_heading_after_a_gap_is_not_an_orphan():
    assert layout.find_orphans([L(100, 50, 540, FULL), L(125, 50, 90, "SKILLS")], right_edge=545) == []


def test_three_word_tail_is_fine():
    assert layout.find_orphans([L(100, 50, 540, FULL), L(112.5, 58, 200, "and Emerging Markets.")], right_edge=545) == []


def test_line_that_did_not_reach_the_edge_does_not_wrap():
    assert layout.find_orphans([L(100, 50, 300, "Short line"), L(112.5, 58, 100, "Two words")], right_edge=545) == []


def test_marker_line_is_not_an_orphan():
    # A line flagged marker=True (a Chrome <li> curve sits left of it) starts its own bullet, even
    # when it's short and the previous line happened to run close to the right edge.
    cur = L(112.5, 58, 140, "Python")
    cur["marker"] = True
    assert layout.find_orphans([L(100, 50, 540, FULL), cur], right_edge=545) == []


def test_mark_nearest_line_marks_only_the_closest_line():
    # Two lines 8pt apart (tight spacing). A curve whose vertical midpoint is 2pt from line1's
    # centre and 6pt from line2's centre must mark only line1 -- not every line whose window
    # happens to contain the curve.
    line1 = {"top": 100, "bottom": 108, "x0": 50, "x1": 200}  # centre 104
    line2 = {"top": 108, "bottom": 116, "x0": 50, "x1": 150}  # centre 112
    curve = {"x0": 40, "x1": 45, "top": 105, "bottom": 107}   # cy 106
    layout.mark_nearest_line([line1, line2], [curve])
    assert line1.get("marker") is True
    assert not line2.get("marker")


try:
    cvlib.find_chrome()
    HAVE_CHROME = True
except RuntimeError:
    HAVE_CHROME = False


CHROME_LI_MARKER_HTML = """<!doctype html>
<html><head><meta charset="utf-8">
<style>
  body { font-family: Arial, sans-serif; font-size: 13px; line-height: 1.38; margin: 0; }
  ul { margin: 0; padding: 0 0 0 18px; }
  li { margin: 2px 0; }
</style></head><body>
<ul>
<li>Designed and delivered scalable backend services for global logistics and supply chain operations worldwide</li>
<li>Python</li>
</ul>
</body></html>"""


@pytest.mark.skipif(not HAVE_CHROME, reason="needs Chrome/Chromium/Edge")
def test_chrome_li_marker_prevents_false_orphan(tmp_path):
    # Repro: a full-width single-line bullet followed by a one-word <li>Python</li>. Chrome draws
    # the bullet glyph as a vector curve rather than text, so without marker detection the short
    # "Python" line looks like a wrapped continuation of the line above it.
    html = tmp_path / "cv.html"
    html.write_text(CHROME_LI_MARKER_HTML, encoding="utf-8")
    pdf = cvlib.render_pdf(html, tmp_path / "cv.pdf")
    assert layout.check(pdf)["orphans"] == []


MULTI_PAGE_MARGINS_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><style>
  @page { size: A4; margin: 20mm; }
  body { font-family: Arial, sans-serif; font-size: 12px; margin: 0; }
  .brk { page-break-after: always; }
  p.j { text-align: justify; }
</style></head><body>
<p class="brk">Hi</p>
<p class="j">This paragraph is deliberately long enough that it wraps onto a second line so the
browser justifies the first line to the full measure of the content box for an accurate margin
test today.</p>
</body></html>"""


TIGHT_WRAPPED_LI_HTML = """<!doctype html>
<html><head><meta charset="utf-8">
<style>
  body { font-family: Arial, sans-serif; font-size: 10px; line-height: 1.15; margin: 0; }
  ul { margin: 0; padding: 0 0 0 14px; max-width: 300px; }
  li { margin: 0; }
</style></head><body>
<ul>
<li>Built contribution pages and pricing feeds for clients across London and worldwide</li>
</ul>
</body></html>"""


@pytest.mark.skipif(not HAVE_CHROME, reason="needs Chrome/Chromium/Edge")
def test_tight_spacing_still_finds_a_genuine_orphan(tmp_path):
    # Repro: a single <li> at 10px/1.15 line-height (as in dense_cv.html) wraps, in a narrow
    # column, to a genuine 2-word orphan last line. At this tight a line-top gap (~9pt) the old
    # top..bottom "window" marker check matched the curve against BOTH the bullet's first line and
    # its wrapped continuation, hiding the real orphan. Only the first line should get marker=True.
    html = tmp_path / "cv.html"
    html.write_text(TIGHT_WRAPPED_LI_HTML, encoding="utf-8")
    pdf = cvlib.render_pdf(html, tmp_path / "cv.pdf")
    assert len(layout.check(pdf)["orphans"]) == 1


@pytest.mark.skipif(not HAVE_CHROME, reason="needs Chrome/Chromium/Edge")
def test_margins_consider_every_page_not_just_the_first(tmp_path):
    # Repro: page 1 holds only a short line ("Hi"); page 2 has a line justified out to the true
    # right margin. Margins computed from page 1 alone would see a huge, wrong right margin and
    # wrongly flag "left/right margins differ".
    html = tmp_path / "cv.html"
    html.write_text(MULTI_PAGE_MARGINS_HTML, encoding="utf-8")
    pdf = cvlib.render_pdf(html, tmp_path / "cv.pdf")
    report = layout.check(pdf)
    assert report["pages"] == 2
    assert abs(report["margins_mm"]["left"] - report["margins_mm"]["right"]) <= 3
    assert not any("margins differ" in p for p in report["problems"])
