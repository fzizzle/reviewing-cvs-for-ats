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
    full = score.contact_checks("Jane Doe\nParis, France · +33 7 54 07 83 76 · jane@example.com · linkedin.com/in/jane")
    assert all(full.values())
    partial = score.contact_checks("Jane Doe\n07826 761326 · jane@example.com")
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
