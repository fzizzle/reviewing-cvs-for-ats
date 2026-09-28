#!/usr/bin/env python3
"""Local ATS simulation for a CV.

Extracts the CV with several parsers (pypdf, pdfminer, pdfplumber, pymupdf for PDF/HTML;
python-docx for .docx; raw text for .txt/.md) and scores each extraction:

  parse quality /65  contact 15, sections 15, section order 10, dates 10, date placement 10,
                     length 5, minus up to 15 for letter-spaced (garbled) text
  keywords      /35  share of advert keywords found (only with --keywords)

This is a heuristic simulation, NOT a commercial ATS score. Always report it as such.

Usage: cvats score CV [--keywords KW.json] [--baseline OLD_CV] [--max-pages N] [--json]

KW.json: {"advert": "short label", "keywords": {"label": ["synonym", ...], ...}}
Synonyms match case-insensitively, across line breaks. Short synonyms (<= 4 chars) match whole words,
plural allowed: "api" matches "APIs", but "ai" does not match "Aim" and "r" does not match "Research".
Longer synonyms match at the start of a word: "manufactur" matches "manufacturing", "ndt" never
matches "roundtable". List "leadership" separately from "lead". Never edit KW.json to raise a score.
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from cvlib import MIN_WORDS, NO_TEXT, cli, docx_header_footer_text, extract_all, normalise  # noqa: E402

MONTH = (r"(?:january|february|march|april|may|june|july|august|september|october|november|december|"
         r"janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|"
         r"décembre|decembre|januar|märz|juni|juli|oktober|dezember|"  # German (others match EN/FR)
         r"enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre|"
         r"jan|feb|fév|fev|mar|mär|apr|avr|jun|jul|juil|aug|sep|sept|oct|okt|nov|dec|déc|dez|ene|abr|ago|dic)\.?")
DATE = (rf"(?:{MONTH}\s+\d{{4}}|(?:19|20)\d{{2}}-(?:0[1-9]|1[0-2])(?!\d)|\d{{1,2}}[./]\d{{4}}"
        rf"|(?:19|20)\d{{2}})")  # "Mar 2020", ISO "2020-03", "03.2020" or "3/2020", "2020"
PRESENT = r"present|current|now|today|aujourd'hui|présent|en\s+cours|heute|aktuell|actualidad|presente"
RANGE = re.compile(rf"(?<!\w)({DATE})\s*(?:–|—|-|to|à)\s*({DATE}|{PRESENT})(?!\w)", re.I)
YEAR_ONLY = re.compile(r"(?:19|20)\d{2}")

SECTIONS = {  # checked in this order; first match wins
    "profile": r"\b(profile|summary|about me|profil|objective)\b",
    "education": r"\b(education|qualifications|formations?|formación|diplômes|ausbildung|educación)\b",
    "experience": (r"\b(experiences?|employment|work history|career history|expériences?|berufserfahrung"
                   r"|experiencias?)\b"),
    "projects": r"\b(projects?|projets?)\b",
    "skills": r"\b(skills|compétences?|competences?|kenntnisse|habilidades)\b",
    "languages": r"\b(languages|langues?|sprachen|idiomas)\b",
    "interests": r"\b(interests|hobbies|loisirs|centres d'intérêt)\b",
}
REQUIRED = ("experience", "education", "skills")
NON_DATED = {"skills", "languages", "interests"}
GARBLED = re.compile(r"(?<!\w)(?:[A-ZÀ-Ý] ){3,}[A-ZÀ-Ý](?!\w)")

ROLE_WORDS = ("manager", "officer", "coordinator", "specialist", "director", "lead", "executive",
              "consultant", "analyst", "supervisor", "administrator", "associate", "assistant",
              "pilot", "representative", "engineer", "technician", "trainer", "teacher", "advisor",
              "adviser", "head", "intern")
ROLE_BLOCKLIST = re.compile(r"\b(?:" + "|".join(ROLE_WORDS) + r")\b", re.I)

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"\+?\d[\d\s().-]{6,}\d")
LINK = re.compile(r"linkedin\.com/|github\.com/|https?://|www\.", re.I)
LOCATION = re.compile(r"(?<!\w)[A-ZÀ-Ý][a-zà-ÿ]+(?:[ -][A-ZÀ-Ý][a-zà-ÿ]+)*,\s*[A-ZÀ-Ý][A-Za-zà-ÿ]+")
CONTACT_WEIGHTS = {"email": 5, "phone": 3, "international_phone": 2, "link": 2.5, "location": 2.5}
COLS = ["total", "parse", "keywords", "contact", "sections", "order", "dates", "placement", "length", "penalty", "words"]


def _synonym_pattern(syn):
    """Short synonyms (<= 4 chars) match whole words, plural allowed; longer ones match word starts."""
    syn = " ".join(syn.lower().split())
    esc = re.escape(syn)
    return r"(?<!\w)" + esc + r"s?(?!\w)" if len(syn) <= 4 else r"(?<!\w)" + esc


def keyword_hits(text, keywords):
    low = " ".join(unicodedata.normalize("NFKC", text).lower().split())  # line breaks become spaces
    return {label: any(re.search(_synonym_pattern(s), low) for s in syns)
            for label, syns in keywords.items()}


def heading_key(line):
    """Section key for a heading line, 'other' for an unknown ALL-CAPS heading, else None.

    A heading starts with a capital: a lowercase line such as "negotiation skills" is a wrapped
    fragment of the line above, not a Skills heading.
    """
    s = line.strip()
    words = s.split()
    if not 1 <= len(words) <= 6 or ":" in s or s.endswith((".", ",", ";")):
        return None
    first_letter = next((c for c in s if c.isalpha()), "")
    if not first_letter.isupper():
        return None
    if ROLE_BLOCKLIST.search(s):
        return None
    for key, pat in SECTIONS.items():
        if re.search(pat, s, re.I):
            return key
    if s.upper() == s and re.search(r"[A-Za-zÀ-ÿ]", s):
        return "other"
    return None


def section_sequence(text):
    seq = []
    for line in text.splitlines():
        key = heading_key(line)
        if key and key != "other" and key not in seq:
            seq.append(key)
    return seq


def date_placement(text):
    """(dates under a sensible section, [(date, section) for dates under skills/languages/interests])."""
    current, ok, bad = None, 0, []
    for line in text.splitlines():
        key = heading_key(line)
        if key:
            current = key
            continue
        for m in RANGE.finditer(line):
            if current in NON_DATED:
                bad.append((m.group(0), current))
            else:
                ok += 1
    return ok, bad


def _phones(text):
    """Phone-like runs with at least 9 digits (so "+25%" or "2019 - 2021" never count)."""
    return [m.group() for m in PHONE.finditer(text) if len(re.sub(r"\D", "", m.group())) >= 9]


def contact_checks(text):
    head = "\n".join([line for line in text.splitlines() if line.strip()][:5])  # contact block only
    phones = _phones(text)
    return {"email": bool(EMAIL.search(text)), "phone": bool(phones),
            "international_phone": any(p.startswith("+") for p in phones), "link": bool(LINK.search(text)),
            "location": bool(LOCATION.search(head))}


def score_text(text, pages, *, keywords=None, expected_dates=1, order_consistent=True, max_pages=2):
    contact = contact_checks(text)
    seq = section_sequence(text)
    missing_sections = [k for k in REQUIRED if k not in seq]
    ranges = [m.group(1) for m in RANGE.finditer(text)]
    monthly = [r for r in ranges if not YEAR_ONLY.fullmatch(r.strip())]
    ok, misplaced = date_placement(text)
    words = len(re.findall(r"\w+", text))
    garbled = GARBLED.findall(text)
    r = {
        "contact": sum(CONTACT_WEIGHTS[k] for k, v in contact.items() if v),
        "sections": round(15 * (len(REQUIRED) - len(missing_sections)) / len(REQUIRED), 1),
        "order": (10 if len(seq) >= 2 else 5) if order_consistent else 0,
        "dates": round(5 * min(1, len(ranges) / max(expected_dates, 1)) + 5 * len(monthly) / len(ranges), 1) if ranges else 0,
        "placement": round(10 * ok / (ok + len(misplaced)), 1) if ok + len(misplaced) else 0,
        "length": (2.5 if pages is None or pages <= max_pages else 0) + (2.5 if 300 <= words <= 900 else 0),
        "penalty": min(3 * len(garbled), 15),
        "words": words, "pages": pages, "garbled": garbled, "sequence": seq,
        "missing_sections": missing_sections, "misplaced_dates": misplaced,
        "missing_contact": [k for k, v in contact.items() if not v],
    }
    r["parse"] = round(max(0.0, r["contact"] + r["sections"] + r["order"] + r["dates"]
                           + r["placement"] + r["length"] - r["penalty"]), 1)
    if keywords:
        hits = keyword_hits(text, keywords)
        r["keywords"] = round(35 * sum(hits.values()) / len(hits), 1)
        r["total"] = round(r["parse"] + r["keywords"], 1)
        r["missing_keywords"] = [k for k, v in hits.items() if not v]
    else:
        r["keywords"] = r["total"] = None
        r["missing_keywords"] = []
    return r


def score_cv(path, keywords=None, max_pages=2):
    texts, pages = extract_all(path)
    texts = normalise(texts)  # idempotent; keeps extract_all's ligature counts
    expected = max(len(RANGE.findall(t)) for t in texts.values()) or 1
    consistent = len({tuple(section_sequence(t)) for t in texts.values()}) == 1
    rows = {n: score_text(t, pages, keywords=keywords, expected_dates=expected,
                          order_consistent=consistent, max_pages=max_pages) for n, t in texts.items()}
    for n, r in rows.items():
        r["ligatures"] = texts.ligatures.get(n, 0)
    if str(path).lower().endswith(".docx") and docx_header_footer_text(path):
        for r in rows.values():
            r["header_footer_text"] = docx_header_footer_text(path)
    return rows


def table(title, rows):
    out = [f"### {title}", "| parser | " + " | ".join(COLS) + " |", "|---|" + "---|" * len(COLS)]
    for name, r in rows.items():
        out.append(f"| {name} | " + " | ".join("—" if r[c] is None else str(r[c]) for c in COLS) + " |")
    return "\n".join(out)


def problems(rows):
    empty = [name for name, r in rows.items() if r["words"] < MIN_WORDS]
    out = [f"- {NO_TEXT} ({', '.join(empty)})"] if empty else []
    for name, r in rows.items():
        if r["missing_sections"]:
            out.append(f"- {name}: section headings not recognised: {', '.join(r['missing_sections'])}")
        if r["garbled"]:
            out.append(f"- {name}: letter-spaced text read as separate letters: {r['garbled'][:3]}")
        if r["misplaced_dates"]:
            out.append(f"- {name}: dates landed under the wrong section: {r['misplaced_dates']}")
        if r["order"] == 0:
            out.append(f"- {name}: parsers disagree on section order: {r['sequence']}")
        if r["missing_contact"]:
            out.append(f"- {name}: contact items not found: {', '.join(r['missing_contact'])}")
        if r.get("ligatures"):
            out.append(f"- parser {name} extracted ligature glyphs ({r['ligatures']}, e.g. one glyph for 'fi'); "
                       "add font-variant-ligatures: none")
    first = next(iter(rows.values()))
    if first.get("header_footer_text"):
        out.append(f"- Word header/footer holds text many ATS skip: {first['header_footer_text']!r}")
    if first["missing_keywords"]:
        out.append("- advert keywords not found: " + ", ".join(first["missing_keywords"]))
    return out


@cli
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cv")
    ap.add_argument("--keywords")
    ap.add_argument("--baseline")
    ap.add_argument("--max-pages", type=int, default=2)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    keywords, advert = None, None
    if a.keywords:
        data = json.loads(Path(a.keywords).read_text(encoding="utf-8"))
        keywords, advert = data["keywords"], data.get("advert")
    report = {"cv": score_cv(a.cv, keywords, a.max_pages)}
    if a.baseline:
        report["baseline"] = score_cv(a.baseline, keywords, a.max_pages)
    if a.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    print("Local ATS simulation (heuristic, not a commercial ATS score)" + (f" — advert: {advert}" if advert else ""))
    for key, title in (("cv", a.cv), ("baseline", f"BASELINE {a.baseline}")):
        if key in report:
            print()
            print(table(title, report[key]))
            for line in problems(report[key]):
                print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
