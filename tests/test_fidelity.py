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
