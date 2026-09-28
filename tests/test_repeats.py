import pytest

import cvlib
import repeats

HTML = """<html><head><title>Jane Doe CV</title><style>li { margin: 0 }</style></head><body>
<h2>Experience</h2><div class="sub">Acme Ltd · Sep 2023 – Apr 2025</div>
<ul><li>Led the migration of billing data.</li><li>Led a team of four analysts.</li>
<li><b>Forecasting:</b> predicted demand with ARIMA.</li></ul>
<p>Data analyst apprentice at Acme. Completed as a data analyst apprentice.</p></body></html>"""


def _load(tmp_path):
    f = tmp_path / "cv.html"
    f.write_text(HTML, encoding="utf-8")
    return repeats.load(f)


def test_html_bullets_and_openers(tmp_path):
    bullets, _ = _load(tmp_path)
    assert len(bullets) == 3
    assert repeats.repeated_openers(bullets) == {"led": 2}  # date line isn't a bullet; label skipped


def test_repeated_phrase(tmp_path):
    _, text = _load(tmp_path)
    assert "data analyst apprentice" in repeats.repeated_phrases(text)


def test_terms_ignore_head(tmp_path):
    _, text = _load(tmp_path)
    assert repeats.term_counts(text, ["Acme", "Jane Doe"]) == {"Acme": 2, "Jane Doe": 0}


def test_allow_list():
    assert repeats.repeated_phrases("python sql excel. python sql excel.", allow=["python", "sql", "excel"]) == []


def test_text_bullets(tmp_path):
    f = tmp_path / "cv.txt"
    f.write_text("• Led x project\n• Led y project\nNot a bullet\n", encoding="utf-8")
    bullets, _ = repeats.load(f)
    assert repeats.repeated_openers(bullets) == {"led": 2}


def test_dates_do_not_create_phrases():
    assert repeats.repeated_phrases("London UK Sep 2023 Apr 2025. London UK Sep 2019 Jun 2023.") == []


try:
    cvlib.find_chrome()
    HAVE_CHROME = True
except RuntimeError:
    HAVE_CHROME = False


CHROME_LI_BULLETS_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><body>
<ul>
<li>Led the migration of billing data.</li>
<li>Led a team of four analysts.</li>
<li>Led quarterly planning with finance.</li>
</ul>
</body></html>"""


@pytest.mark.skipif(not HAVE_CHROME, reason="needs Chrome/Chromium/Edge")
def test_pdf_bullets_from_chrome_li_markers(tmp_path):
    # Repro: the same CV as .html reports 3 bullets, but as a Chrome-rendered PDF it reported 0
    # (and exited 0, a silent clean pass) because Chrome draws <li> markers as vector curves, not
    # bullet glyphs in the text stream. load() must fall back to layout.page_lines()'s marker flag.
    html = tmp_path / "cv.html"
    html.write_text(CHROME_LI_BULLETS_HTML, encoding="utf-8")
    pdf = cvlib.render_pdf(html, tmp_path / "cv.pdf")
    bullets, _ = repeats.load(pdf)
    assert repeats.repeated_openers(bullets) == {"led": 3}


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
def test_tight_spacing_wrapped_li_is_one_bullet_not_two(tmp_path):
    # Repro: at tight line spacing (10px/1.15, as in dense_cv.html), a single wrapped <li> was
    # split into two "bullets" because the old marker window matched the curve to both the
    # bullet's first line and its wrapped continuation line.
    html = tmp_path / "cv.html"
    html.write_text(TIGHT_WRAPPED_LI_HTML, encoding="utf-8")
    pdf = cvlib.render_pdf(html, tmp_path / "cv.pdf")
    bullets, _ = repeats.load(pdf)
    assert len(bullets) == 1


MANAGED = ["Managed weekly stock count for the ward pharmacy.",
           "Managed rota changes for twelve healthcare assistants.",
           "Managed weekly stock count audits with the matron."]


def _docx_table_list_bullets(path):
    import docx
    d = docx.Document()
    d.add_paragraph("Experience")
    cell = d.add_table(rows=1, cols=1).cell(0, 0)
    cell.paragraphs[0].text = MANAGED[0]
    cell.paragraphs[0].style = d.styles["List Bullet"]
    for text in MANAGED[1:]:
        cell.add_paragraph(text, style="List Bullet")
    d.save(path)
    return path


def _docx_typed_glyphs(path):
    import docx
    d = docx.Document()
    for text in MANAGED:
        d.add_paragraph("• " + text)  # Normal style, glyph typed by hand
    d.save(path)
    return path


def _docx_numpr_normal(path):
    import docx
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    d = docx.Document()
    for text in MANAGED:
        para = d.add_paragraph(text)  # Normal style, but numbered via direct formatting
        num_pr = OxmlElement("w:numPr")
        for tag, val in (("w:ilvl", "0"), ("w:numId", "1")):
            el = OxmlElement(tag)
            el.set(qn("w:val"), val)
            num_pr.append(el)
        para._p.get_or_add_pPr().append(num_pr)
    d.save(path)
    return path


@pytest.mark.parametrize("build", [_docx_table_list_bullets, _docx_typed_glyphs, _docx_numpr_normal])
def test_docx_bullets_in_tables_typed_glyphs_and_numpr(tmp_path, build):
    # Repro: load() only looked at top-level paragraphs with a "List" style, so bullets in a table
    # cell, typed "• " bullets and numPr-numbered Normal paragraphs all read as zero bullets (a false pass).
    bullets, _ = repeats.load(build(tmp_path / "cv.docx"))
    assert repeats.repeated_openers(bullets) == {"managed": 3}


def test_docx_table_cell_text_is_checked_for_phrases(tmp_path):
    _, text = repeats.load(_docx_table_list_bullets(tmp_path / "cv.docx"))
    phrases = repeats.repeated_phrases(text)
    assert "managed weekly stock" in phrases and "weekly stock count" in phrases


def test_zero_bullet_warning_for_every_format(tmp_path, capsys):
    f = tmp_path / "cv.txt"
    f.write_text("Experience\n" + " ".join(f"word{i}" for i in range(40)) + "\n", encoding="utf-8")
    repeats.main([str(f)])
    assert "warning: no bullets detected" in capsys.readouterr().out


def test_non_latin_words_are_counted():
    # Repro: WORD only knew a-z and à-ÿ, so Cyrillic text produced no words and no phrases.
    text = "управление проектами компании. управление проектами компании."
    assert repeats.repeated_phrases(text) == ["управление проектами компании"]


def test_word_keeps_polish_letters_and_programming_names():
    assert repeats.WORD.findall("zarządzanie c++ c#") == ["zarządzanie", "c++", "c#"]
