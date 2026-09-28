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
