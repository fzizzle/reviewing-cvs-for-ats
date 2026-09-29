import json
import pytest

import score


def test_keywords_match_word_starts_only():
    hits = score.keyword_hits("Co-led a roundtable on manufacturing; CAD (Onshape).",
                              {"NDT": ["ndt"], "manufacturing": ["manufactur"], "CAD": ["cad"]})
    assert hits == {"NDT": False, "manufacturing": True, "CAD": True}


def test_letter_spaced_heading_is_garbled_and_not_a_section():
    r = score.score_text("W O R K E X P E R I E N C E\nEngineer at Acme\nEDUCATION\nBSc\nSKILLS\nPython", 1)
    assert r["garbled"] and r["penalty"] == 3
    assert r["missing_sections"] == ["experience"]


def test_date_under_skills_is_misplaced():
    ok, bad = score.date_placement("EXPERIENCE\nEngineer\nJan 2020 – Mar 2021\nSKILLS\nJun 2017 – Jun 2019\nPython")
    assert ok == 1 and bad == [("Jun 2017 – Jun 2019", "skills")]


def test_month_dates_score_higher_than_years_only():
    base = "EXPERIENCE\nEngineer\n{}\nEDUCATION\nBSc\nSKILLS\nPython"
    assert score.score_text(base.format("Sep 2023 – Apr 2025"), 1)["dates"] == 10
    assert score.score_text(base.format("2023 – 2025"), 1)["dates"] == 5


def test_marketing_word_is_not_a_month():
    assert score.score_text("EXPERIENCE\nMarketing 2019 – 2021\nSKILLS\nx", 1)["dates"] == 5


def test_contact_checks():
    full = score.contact_checks("Jane Doe\nParis, France · +33 6 39 98 12 34 · jane@example.com · linkedin.com/in/jane")
    assert all(full.values())
    partial = score.contact_checks("Jane Doe\n07700 900123 · jane@example.com")
    assert partial["phone"] and not partial["international_phone"] and not partial["location"]


def test_french_headings_recognised():
    seq = score.section_sequence("EXPÉRIENCE PROFESSIONNELLE\nx\nFORMATION\ny\nCOMPÉTENCES\nz")
    assert seq == ["experience", "education", "skills"]


def test_label_lines_are_not_headings():
    assert score.heading_key("Languages: English (native), Spanish (B2)") is None
    assert score.heading_key("SKILLS") == "skills"
    assert score.heading_key("ENGINEERING PROJECTS") == "projects"


def test_keyword_score_and_total():
    text = "EXPERIENCE\nUsed HubSpot and GA4\nEDUCATION\nBA\nSKILLS\nSEO"
    r = score.score_text(text, 1, keywords={"HubSpot": ["hubspot"], "SQL": ["sql"]})
    assert r["keywords"] == 17.5 and r["missing_keywords"] == ["SQL"]
    assert r["total"] == round(r["parse"] + 17.5, 1)


def test_job_titles_are_not_headings():
    assert score.heading_key("Skills Development Officer") is None
    assert score.heading_key("PROJECT MANAGER") is None
    assert score.heading_key("Formation Pilot") is None
    assert score.heading_key("ENGINEERING PROJECTS") == "projects"
    assert score.heading_key("WORK EXPERIENCE") == "experience"


def test_line_wrap_variant_does_not_break_order():
    a = score.section_sequence("EXPERIENCE\nProject Manager\nJan 2020 - Mar 2022\nEDUCATION\nBSc\nSKILLS\nPython")
    b = score.section_sequence("EXPERIENCE\nProject Manager Jan 2020 - Mar 2022\nEDUCATION\nBSc\nSKILLS\nPython")
    assert a == b == ["experience", "education", "skills"]


def test_score_cv_zeroes_order_when_parsers_disagree(monkeypatch):
    def fake_extract_all(path):
        return ({"a": "EXPERIENCE\nEngineer\nEDUCATION\nBSc\nSKILLS\nPython",
                 "b": "EDUCATION\nBSc\nEXPERIENCE\nEngineer\nSKILLS\nPython"}, 1)
    monkeypatch.setattr(score, "extract_all", fake_extract_all)
    rows = score.score_cv("dummy.txt")
    assert rows["a"]["order"] == 0 and rows["b"]["order"] == 0


def test_score_cv_full_order_when_parsers_agree(monkeypatch):
    text = "EXPERIENCE\nEngineer\nEDUCATION\nBSc\nSKILLS\nPython"
    monkeypatch.setattr(score, "extract_all", lambda path: ({"a": text, "b": text}, 1))
    rows = score.score_cv("dummy.txt")
    assert rows["a"]["order"] == 10 and rows["b"]["order"] == 10


LIGATURE_CV = "{}\nx\nExperience\nEngineer\nEducation\nBSc\nSkills\nPython"


def test_ligature_glyphs_are_normalised_before_scoring(monkeypatch):
    # Repro: a parser that kept the fi-ligature glyph (U+FB01) missed the "Profile" heading, so the
    # parsers "disagreed" on section order and both rows lost all 10 order points.
    monkeypatch.setattr(score, "extract_all", lambda path: (
        {"a": LIGATURE_CV.format("Pro\ufb01le"), "b": LIGATURE_CV.format("Profile")}, 1))
    rows = score.score_cv("dummy.txt")
    assert rows["a"]["order"] == 10 and rows["b"]["order"] == 10
    assert rows["a"]["ligatures"] == 1 and rows["b"]["ligatures"] == 0
    lines = [line for line in score.problems(rows) if "ligature" in line]
    assert len(lines) == 1 and "a" in lines[0] and "font-variant-ligatures: none" in lines[0]


def test_keyword_found_through_ligature():
    assert score.keyword_hits("Certi\ufb01ed welder", {"certified": ["certified"]}) == {"certified": True}


def test_template_turns_off_ligatures():
    import pathlib
    import re
    css = (pathlib.Path(__file__).resolve().parents[1] / "templates" / "cv-template.html").read_text(encoding="utf-8")
    body_rule = re.search(r"\bbody\s*\{([^}]*)\}", css).group(1)
    assert "font-variant-ligatures: none" in body_rule


def test_short_synonyms_match_whole_words_only():
    kw = {s: [s] for s in ("cro", "r", "go", "ai", "sap")}
    assert score.keyword_hits("cross-functional Research Good Aim Sapient", kw) == {s: False for s in kw}


def test_short_synonyms_allow_plural_and_punctuation():
    kw = {s: [s] for s in ("r", "api", "sql", "ga4")}
    assert score.keyword_hits("R, APIs, SQL-based, GA4", kw) == {s: True for s in kw}


def test_multiword_keywords_survive_line_breaks_and_slashes():
    kw = {"PM": ["project management"], "A/B": ["a/b test"]}
    assert score.keyword_hits("Led project\nmanagement and a/b testing", kw) == {"PM": True, "A/B": True}


def test_lowercase_wrapped_fragment_is_not_a_heading():
    # Repro: a bullet wrapped so "negotiation skills" sat on its own line; it read as a Skills
    # heading, and the next role's dates were then flagged as "under skills".
    assert score.heading_key("negotiation skills") is None
    assert score.heading_key("Work experience") == "experience"
    ok, bad = score.date_placement("Experience\nAcme Jan 2021 – Present\npresentation and\nnegotiation skills\n"
                                   "Beta Jan 2019 – Feb 2021\nEducation\nBSc")
    assert ok == 2 and bad == []


GERMAN_CV = ("BERUFSERFAHRUNG\nIngenieurin, Beispiel GmbH, 03.2019 – heute\n"
             "Praktikantin, Muster AG, 09.2017 – 02.2019\n"
             "AUSBILDUNG\nM.Sc. Maschinenbau, TU Beispiel, 10.2015 – 09.2017\nKENNTNISSE\nCAD, Python")


def test_german_numeric_dates_and_heute():
    r = score.score_text(GERMAN_CV, 1, expected_dates=3)
    assert r["dates"] == 10 and r["placement"] == 10


def test_french_plural_headings_recognised():
    seq = score.section_sequence("EXPÉRIENCES PROFESSIONNELLES\nx\nFORMATIONS\ny\nCOMPÉTENCES\nz")
    assert seq == ["experience", "education", "skills"]


def test_spanish_heading_and_month_range():
    assert score.heading_key("FORMACIÓN") == "education"
    assert score.heading_key("EXPERIENCIAS") == "experience"
    assert score.RANGE.search("Analista, enero 2019 – actualidad").group(0) == "enero 2019 – actualidad"


def test_german_and_iso_months_are_ranges():
    for text in ("März 2020 – Dezember 2022", "Okt. 2018 - aktuell", "2019-03 – 2021-06",
                 "Mayo 2020 – en cours", "dic 2019 – presente"):
        assert score.RANGE.fullmatch(text), text
    assert score.RANGE.search("Chicago 2019") is None


def test_keyword_example_keeps_one_tool_per_label():
    import json
    import pathlib
    path = pathlib.Path(__file__).resolve().parents[1] / "templates" / "keywords-example.json"
    kw = json.loads(path.read_text(encoding="utf-8"))["keywords"]
    assert kw["HubSpot"] == ["hubspot"] and kw["Salesforce Marketing Cloud"] == ["salesforce"]
    assert not any("/" in label and "A/B" not in label for label in kw)  # no OR-merged tool labels


def test_percentage_is_not_an_international_prefix():
    r = score.contact_checks("07700 900123\nGrew sales +25%")
    assert r["phone"] and r["international_phone"] is False


FULL = ("Jane Doe\nParis, France · +33 6 39 98 12 34 · jane@example.com · linkedin.com/in/jane\n"
        "EXPERIENCE\nEngineer\nJan 2020 – Mar 2021\nEDUCATION\nBSc\nSKILLS\nPython")
KW = {"SQL": ["sql"], "Python": ["python"]}
NO_CITY = FULL.replace("Paris, France · ", "")


def test_problems_print_a_shared_message_once_with_its_parsers():
    rows = {"a": score.score_text(NO_CITY, 1, keywords=KW), "b": score.score_text(NO_CITY, 1, keywords=KW),
            "c": score.score_text(FULL, 1, keywords=KW)}
    lines = score.problems(rows)
    assert "- contact items not found: location (a, b)" in lines
    assert sum("contact items not found" in line for line in lines) == 1


def test_problems_say_all_parsers_when_every_parser_hits():
    rows = {n: score.score_text(NO_CITY, 1) for n in ("a", "b")}
    assert "- contact items not found: location (all parsers)" in score.problems(rows)


def test_keyword_missed_by_some_parsers_is_a_layout_problem():
    rows = {"a": score.score_text(FULL, 1, keywords=KW),
            "b": score.score_text(FULL.replace("Python", "P y t h o n"), 1, keywords=KW)}
    lines = score.problems(rows)
    assert "- advert keywords not found: SQL" in lines
    assert "- advert keywords some parsers miss (a layout problem, not a gap): Python (b)" in lines


def test_section_order_disagreement_is_one_line(monkeypatch):
    monkeypatch.setattr(score, "extract_all", lambda path, **_: (
        {"a": "EXPERIENCE\nx\nEDUCATION\ny\nSKILLS\nz", "b": "EDUCATION\ny\nEXPERIENCE\nx\nSKILLS\nz",
         "c": "EXPERIENCE\nx\nEDUCATION\ny\nSKILLS\nz"}, 1))
    lines = [line for line in score.problems(score.score_cv("dummy.txt")) if "disagree" in line]
    assert lines == ["- parsers disagree on section order: a, c ['experience', 'education', 'skills']; "
                     "b ['education', 'experience', 'skills']"]


def _kw_file(tmp_path, data):
    p = tmp_path / "kw.json"
    p.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    return p


@pytest.mark.parametrize("data, needle", [
    ({"advert": "x", "kw": {"SQL": ["sql"]}}, '"keywords"'),
    ({"keywords": {}}, '"keywords"'),
    ("[1, 2]", '"keywords"'),
    ({"keywords": {"SQL": "sql"}}, 'keyword "SQL" needs a list'),
    ({"keywords": {"SQL": []}}, 'keyword "SQL" needs a list'),
    ({"keywords": {"SQL": ["sql"]}, "required": ["Python"]}, "unknown: ['Python']"),
])
def test_bad_keyword_files_are_clean_errors(tmp_path, capsys, data, needle):
    cv = tmp_path / "cv.txt"
    cv.write_text("EXPERIENCE\nAnalyst using sql\n", encoding="utf-8")
    assert score.main([str(cv), "--keywords", str(_kw_file(tmp_path, data))]) == 2
    err = capsys.readouterr().err
    assert err.startswith("cvats: error:") and needle in err


def test_required_keywords_count_double_and_are_listed_first():
    text = "EXPERIENCE\nUsed HubSpot\nEDUCATION\nBA\nSKILLS\nSEO"
    kw = {"HubSpot": ["hubspot"], "SQL": ["sql"], "GA4": ["ga4"]}
    r = score.score_text(text, 1, keywords=kw, required=("SQL",))
    assert r["keywords"] == round(35 * 1 / 4, 1)  # HubSpot found; weights HubSpot 1 + SQL 2 + GA4 1
    assert r["missing_required"] == ["SQL"]
    lines = score.problems({"a": r})
    assert lines.index("- required advert keywords not found: SQL") < lines.index("- advert keywords not found: GA4")


def test_keyword_example_loads_and_marks_required():
    import pathlib
    path = pathlib.Path(__file__).resolve().parents[1] / "templates" / "keywords-example.json"
    kw, advert, required = score.load_keywords(path)
    assert advert and set(required) <= set(kw) and "team leadership" in required


@pytest.mark.parametrize("text, syn", [
    ("Optimisation of stock levels", "optimization"), ("optimized pricing", "optimise"),
    ("Analysed sales data", "analyze"), ("carbon fibre layup", "carbon fiber"), ("Colour matching", "color"),
    ("Expérience client", "experience client"), ("Gestion de la qualité", "qualite"),
    ("Financial modelling", "modeling"), ("graduate programme", "program"),
])
def test_keywords_match_across_accents_and_uk_us_spelling(text, syn):
    assert score.keyword_hits(text, {"k": [syn]}) == {"k": True}


def test_folding_does_not_create_false_matches():
    assert score.keyword_hits("your hour of flour", {"k": ["yor"]}) == {"k": False}


def test_keyword_found_only_in_skills_is_reported():
    text = "Jane Doe\nEXPERIENCE\nAnalyst\nBuilt dashboards in Tableau\nEDUCATION\nBSc\nSKILLS\nSQL, Tableau"
    r = score.score_text(text, 1, keywords={"SQL": ["sql"], "Tableau": ["tableau"]})
    assert r["listed_only_keywords"] == ["SQL"]
    assert ("- advert keywords only in the header, profile or skills list (add a bullet showing where each "
            "was used, if the person confirms one): SQL") in score.problems({"a": r})
