import json

import fidelity

ORIGINAL = """Priya Shah
Marketing Manager | Digital | CRM
07700 900123 | priya.shah@example.com
PROFILE
Marketing manager with 6 years in B2B SaaS marketing.
EXPERIENCE
Marketing Manager, Brightloop Ltd, Manchester, 2021 – 2024
• Led a team of 4 marketers across content, email and paid social.
• Grew organic traffic by 120% in 18 months.
• Helped with SEO keyword research.
• Ran HubSpot email campaigns reaching 40,000 contacts.
EDUCATION
BA (Hons) Business and Marketing, University of Leeds, 2015 – 2018
SKILLS
HubSpot, GA4, Canva, WordPress, SEO
"""

NEW = """Priya Shah
Marketing Manager · B2B SaaS
Manchester, UK · +44 7700 900123 · priya.shah@example.com
PROFILE
Marketing manager with 6 years in B2B SaaS marketing, owning demand generation.
EXPERIENCE
Marketing Manager, Brightloop Ltd, Manchester, Mar 2021 – 2024
• Led a team of 4 marketers (3+ direct reports) across content, email and paid social.
• Grew organic traffic by 120% in 18 months.
• Led SEO keyword research and SQL funnel analysis.
• Ran HubSpot email campaigns reaching 40,000 contacts.
EDUCATION
BA (Hons) Business and Marketing, University of Leeds, 2015 – 2018
SKILLS
HubSpot, GA4, Canva, WordPress, SEO
"""

KW = {"demand generation": ["demand gen"], "SQL": ["sql"], "HubSpot": ["hubspot"]}
ALL_ITEMS = {"keyword:demand generation", "keyword:SQL", "contact:location", "contact:international_phone",
             "number:3+", "date:2021-03", "term:SQL", "supporting-verbs"}


def _files(tmp_path, original, new):
    o, n = tmp_path / "original.txt", tmp_path / "new.txt"
    o.write_text(original, encoding="utf-8")
    n.write_text(new, encoding="utf-8")
    return o, n


def test_fidelity_lists_every_new_fact():
    items = dict(fidelity.findings({"text": ORIGINAL}, {"text": NEW}, keywords=KW))
    assert set(items) == ALL_ITEMS
    assert items["contact:location"] == "'Manchester, UK'"


def test_numbers_ignore_phones_dates_and_thousand_separators():
    text = "Call +44 20 7946 0123. Jan 2020 – Mar 2021: 40,000 users, 40 000 visits, 25 %, 3+ reports, £1.2m, £2000"
    assert fidelity.numbers(text) == {"40000", "25%", "3+", "£1.2m", "£2000"}


def test_month_years_read_every_date_style():
    text = "Mar 2021 – Present, mars 2020, 03/2019, 2018-11, Summer 2017, 2016, juillet 2015"
    assert fidelity.month_years(text) == {"2021-03", "2020-03", "2019-03", "2018-11", "2015-07"}


def test_confirmed_items_pass_and_exit_code(tmp_path, capsys):
    orig, new = _files(tmp_path, ORIGINAL, NEW)
    kw = tmp_path / "kw.json"
    kw.write_text(json.dumps({"keywords": KW}), encoding="utf-8")
    assert fidelity.main([str(orig), str(new), "--keywords", str(kw)]) == 1
    out = capsys.readouterr().out
    assert "- keyword:demand generation  [UNCONFIRMED]" in out and "unconfirmed: 8" in out
    assert fidelity.main([str(orig), str(new), "--keywords", str(kw), "--confirmed", ",".join(sorted(ALL_ITEMS))]) == 0
    assert "unconfirmed: 0  confirmed: 8" in capsys.readouterr().out


def test_unknown_confirmed_item_is_noted(tmp_path, capsys):
    orig, new = _files(tmp_path, ORIGINAL, ORIGINAL)
    assert fidelity.main([str(orig), str(new), "--confirmed", "number:99"]) == 0
    assert "--confirmed items not found (typo?): number:99" in capsys.readouterr().out


def test_identical_cvs_pass(tmp_path):
    orig, new = _files(tmp_path, ORIGINAL, ORIGINAL)
    assert fidelity.main([str(orig), str(new)]) == 0


def _items(original, new):
    return dict(fidelity.findings({"text": original}, {"text": new}))


def test_changed_email_is_flagged():
    new = ORIGINAL.replace("priya.shah@example.com", "wrong@example.com")
    assert "contact:email" in _items(ORIGINAL, new)


def test_email_case_change_is_not_flagged():
    assert _items(ORIGINAL, ORIGINAL.replace("priya.shah@example.com", "Priya.Shah@Example.com")) == {}


def test_changed_phone_is_flagged():
    new = ORIGINAL.replace("07700 900123", "07700 900456")
    assert "contact:phone" in _items(ORIGINAL, new)


def test_reformatted_phone_is_not_flagged():
    assert _items(ORIGINAL, ORIGINAL.replace("07700 900123", "(07700) 900-123")) == {}


def test_international_form_of_same_phone_is_only_international():
    items = _items(ORIGINAL, ORIGINAL.replace("07700 900123", "+44 7700 900123"))
    assert set(items) == {"contact:international_phone"}
    original = ORIGINAL.replace("07700 900123", "+44 7700 900123")
    assert _items(original, ORIGINAL) == {}


def test_international_form_of_different_phone_is_flagged():
    items = _items(ORIGINAL, ORIGINAL.replace("07700 900123", "+44 7700 900999"))
    assert {"contact:phone", "contact:international_phone"} <= set(items)


def test_changed_link_is_flagged():
    original = ORIGINAL.replace("| priya.shah@example.com", "| priya.shah@example.com | linkedin.com/in/priya-shah")
    assert _items(original, original.replace("linkedin.com/in/priya-shah", "https://www.LinkedIn.com/in/priya-shah/")) == {}
    assert "contact:link" in _items(original, original.replace("priya-shah", "someone-else"))


def test_changed_employment_year_is_flagged():
    new = ORIGINAL.replace("2021 – 2024", "2020 – 2024")
    assert "date:2020" in _items(ORIGINAL, new)


def test_changed_year_present_elsewhere_is_flagged_per_entry():
    # 2018 appears in the original (education), but not on the employment line
    new = ORIGINAL.replace("Manchester, 2021 – 2024", "Manchester, 2018 – 2024")
    assert "date:2018" in _items(ORIGINAL, new)


def test_redated_month_year_reports_only_the_month_item():
    new = ORIGINAL.replace("Manchester, 2021 – 2024", "Manchester, Mar 2019 – 2024")
    items = _items(ORIGINAL, new)
    assert "date:2019-03" in items and "date:2019" not in items


def test_reformatted_dates_are_not_flagged():
    original = ORIGINAL.replace("Manchester, 2021 – 2024", "Manchester, Sept 2021 – 2024")
    for form in ("Sep 2021", "09/2021", "2021-09", "September 2021"):
        assert _items(original, original.replace("Sept 2021", form)) == {}, form


def test_years_ignore_numbers_and_contacts():
    assert fidelity.years("Call 020 7946 0123; £2019 budget, 2019% growth; 1949 and 2101; 2015 – 2018, 03/2019") == \
        {"2015", "2018", "2019"}


def test_accented_capitals_are_not_split():
    original = ORIGINAL.replace("University of Leeds", "ÉCOLE CENTRALE, MÜNCHEN, FRANÇOIS")
    assert fidelity.terms("ÉCOLE MÜNCHEN FRANÇOIS") == {"ÉCOLE", "MÜNCHEN", "FRANÇOIS"}
    assert _items(original, original) == {}


def test_unknown_caps_line_terms_are_checked():
    new = ORIGINAL.replace("SKILLS\n", "SKILLS\nAWS CERTIFIED\n")
    assert "term:AWS" in _items(ORIGINAL, new)


def test_known_section_heading_terms_are_skipped():
    new = ORIGINAL.replace("SKILLS\n", "KEY SKILLS\n")
    assert _items(ORIGINAL, new) == {}


def test_deleted_supporting_bullet_is_fine():
    new = ORIGINAL.replace("• Helped with SEO keyword research.\n", "")
    assert _items(ORIGINAL, new) == {}


def test_upgraded_supporting_bullet_is_flagged():
    new = ORIGINAL.replace("Helped with SEO keyword research.", "Owned SEO keyword research.")
    items = _items(ORIGINAL, new)
    assert set(items) == {"supporting-verbs"} and "Helped with SEO keyword research" in items["supporting-verbs"]


def test_supporting_bullet_kept_with_other_supporting_verb_is_fine():
    new = ORIGINAL.replace("Helped with SEO keyword research.", "Supported SEO keyword research.")
    assert _items(ORIGINAL, new) == {}


def test_docx_original_includes_header_contacts(tmp_path):
    from pathlib import Path
    orig = Path(__file__).parent / "fixtures" / "nurse_cv.docx"
    body = "\n".join(fidelity.cv_texts(orig).values())
    assert "jordan.lee@example.com" in body
    new = tmp_path / "new.txt"
    new.write_text("Jordan Lee\njordan.lee@example.com · +44 161 496 0123\n", encoding="utf-8")
    items = dict(fidelity.findings(fidelity.cv_texts(orig), {"text": new.read_text()}))
    assert not [k for k in items if k.startswith("contact:")], items


def test_german_month_spellings_are_month_dates():
    import fidelity
    for word in ("März", "Maerz", "Jänner", "Februar", "févr.", "Dez."):
        assert fidelity._month(word) is not None, word


def test_job_titles_are_not_supporting_verbs():
    import fidelity
    orig = ["Sales Assistant, Hollins Department Store, York 2015 – 2018",
            "IT Support Analyst, Northwind Media, Leeds 2018 – 2021",
            "Helped with visual merchandising and seasonal window displays."]
    new = ["Sales Assistant", "Hollins Department Store · York · 2015 – 2018",
           "IT Support Analyst", "Northwind Media · Leeds · 2018 – 2021",
           "Contributed to visual merchandising and seasonal window displays."]
    assert fidelity.supporting_upgrades(orig, new) == []
    # The real upgrade is still caught, in English and French.
    assert fidelity.supporting_upgrades(["Helped with visual merchandising and window displays."],
                                        ["Led visual merchandising and window displays."])
    assert fidelity.supporting_upgrades(["Aidé à la mise en place d'un plan d'essais de traction."],
                                        ["Mis en place un plan d'essais de traction."])
