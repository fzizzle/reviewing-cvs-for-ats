#!/usr/bin/env python3
"""Local ATS simulation for a CV.

Extracts the CV with several parsers (pypdf, pdfminer, pdfplumber, pymupdf for PDF/HTML;
python-docx and docx-xml for .docx; raw text for .txt/.md) and scores each extraction:

  parse quality /65  contact 15, sections 15, section order 10, dates 10, date placement 10,
                     length 5, minus up to 15 for letter-spaced (garbled) text and unreadable glyphs
  keywords      /35  share of advert keywords found (only with --keywords)

This is a heuristic simulation, NOT a commercial ATS score. Always report it as such.

Usage: cvats score CV [--keywords KW.json] [--baseline OLD_CV] [--max-pages N] [--json]

KW.json: {"advert": "short label", "keywords": {"label": ["synonym", ...], ...}, "required": ["label", ...]}
("required" is optional; those labels count double in the keyword score and are reported first.)
Synonyms match case-insensitively, across line breaks, ignoring accents and UK/US spelling (optimise/optimize, fibre/fiber, colour/color, modelling/modeling). Short synonyms (<= 4 chars) match whole words,
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
from cvlib import MIN_WORDS, NO_TEXT, cli, docx_header_footer_text, docx_textbox_text, extract_all, normalise  # noqa: E402
from layout import pdf_findings  # noqa: E402

MONTH = (r"(?:january|february|march|april|may|june|july|august|september|october|november|december|"
         r"janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|"
         r"décembre|decembre|januar|märz|juni|juli|oktober|dezember|"  # German (others match EN/FR)
         r"enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre|"
         r"jan|feb|fév|fev|mar|mär|apr|avr|jun|jul|juil|aug|sep|sept|oct|okt|nov|dec|déc|dez|ene|abr|ago|dic)\.?")
SEASON = (r"(?:spring|summer|autumn|fall|winter|printemps|été|ete|automne|hiver|frühling|sommer|herbst"
          r"|primavera|verano|otoño|invierno)")
DATE = (rf"(?:{MONTH}\s+\d{{4}}|{SEASON}\s+\d{{4}}|(?:19|20)\d{{2}}-(?:0[1-9]|1[0-2])(?!\d)|\d{{1,2}}[./]\d{{4}}"
        rf"|(?:19|20)\d{{2}})")  # "Mar 2020", "Summer 2020", ISO "2020-03", "03.2020" or "3/2020", "2020"
PRESENT = r"present|current|now|today|aujourd'hui|présent|en\s+cours|heute|aktuell|actualidad|presente"
RANGE = re.compile(rf"(?<!\w)({DATE})\s*(?:–|—|-|to|à)\s*({DATE}|{PRESENT})(?!\w)", re.I)
YEAR_ONLY = re.compile(r"(?:19|20)\d{2}")

SECTIONS = {  # checked in this order; first match wins
    "profile": r"\b(profile|summary|about me|profil|perfil|objective|personal statement)\b",
    "education": (r"\b(education|qualifications|formations?|formación|diplômes|ausbildung|educación"
                  r"|academic background|études)\b"),
    "experience": (r"\b(experiences?|employment|work history|career history|professional background"
                   r"|internships?|stages|expériences?|berufserfahrung|praktika|experiencias?)\b"),
    "projects": r"\b(projects?|projets?)\b",
    "skills": (r"\b(skills|competencies|compétences?|competences?|competencias|expertise|kenntnisse|fähigkeiten"
               r"|habilidades|tools|technologies)\b"),
    "languages": r"\b(languages|langues?|sprachen|idiomas)\b",
    "interests": r"\b(interests|hobbies|loisirs|centres d'intérêt)\b",
    "certifications": r"\b(certifications?|certificates|licen[cs]es|zertifikate|certificaciones)\b",
    "awards": r"\b(awards|achievements|prix|distinctions)\b",
    "publications": r"\b(publications)\b",
    "volunteering": r"\b(volunteering|volunteer work|bénévolat|ehrenamt|voluntariado)\b",
    "activities": r"\b(activities|extracurriculars?|leadership|activités)\b",
}
REQUIRED = ("experience", "education", "skills")
NON_DATED = {"skills", "languages", "interests"}
GARBLED = re.compile(r"(?<!\w)(?:[A-ZÀ-Ý] ){3,}[A-ZÀ-Ý](?!\w)")
UNREADABLE = re.compile(r"\(cid:\d+\)|[\ue000-\uf8ff\ufffd]")  # unmapped font glyphs, icon-font symbols

ROLE_WORDS = ("manager", "officer", "coordinator", "specialist", "director", "lead", "executive",
              "consultant", "analyst", "supervisor", "administrator", "associate", "assistant",
              "pilot", "representative", "engineer", "technician", "trainer", "teacher", "advisor",
              "adviser", "head", "intern")
ROLE_BLOCKLIST = re.compile(r"\b(?:" + "|".join(ROLE_WORDS) + r")\b", re.I)

COUNTRY_NAMES = (
    "Afghanistan Albania Algeria Andorra Angola Argentina Armenia Australia Austria Azerbaijan Bahrain Bangladesh "
    "Belarus Belgium Bolivia Bosnia Botswana Brazil Brunei Bulgaria Cambodia Cameroon Canada Chile China Colombia "
    "Croatia Cuba Cyprus Czechia Denmark Ecuador Egypt England Estonia Ethiopia Finland France Georgia Germany "
    "Ghana Greece Guatemala Hungary Iceland India Indonesia Iran Iraq Ireland Israel Italy Jamaica Japan Jordan "
    "Kazakhstan Kenya Kosovo Kuwait Latvia Lebanon Libya Lithuania Luxembourg Malaysia Malta Mauritius Mexico "
    "Moldova Monaco Mongolia Montenegro Morocco Mozambique Myanmar Namibia Nepal Netherlands Nigeria Norway Oman "
    "Pakistan Panama Paraguay Peru Philippines Poland Portugal Qatar Romania Russia Rwanda Scotland Senegal Serbia "
    "Singapore Slovakia Slovenia Spain Sweden Switzerland Syria Taiwan Tanzania Thailand Tunisia Turkey Türkiye "
    "Uganda Ukraine Uruguay Uzbekistan Venezuela Vietnam Wales Yemen Zambia Zimbabwe "
    # French, German and Spanish names that differ from the English ones
    "Algérie Allemagne Angleterre Autriche Belgique Brésil Chine Chypre Croatie Danemark Écosse Égypte Espagne "
    "Grèce Hongrie Inde Irlande Italie Japon Liban Malaisie Maroc Mexique Norvège Pologne Roumanie Russie Suède "
    "Suisse Tunisie Turquie Deutschland Österreich Schweiz Frankreich Spanien Italien Niederlande Belgien Polen "
    "Schweden Dänemark España Francia Alemania Italia Suiza México Brasil Perú"
).split() + [
    "United Kingdom", "United States", "United States of America", "United Arab Emirates", "New Zealand",
    "South Africa", "South Korea", "Saudi Arabia", "Hong Kong", "Sri Lanka", "Costa Rica", "Czech Republic",
    "Dominican Republic", "Northern Ireland", "Ivory Coast", "Côte d'Ivoire", "North Macedonia", "Royaume-Uni",
    "États-Unis", "Pays-Bas", "Nouvelle-Zélande", "Émirats arabes unis", "Afrique du Sud", "Arabie saoudite",
    "Vereinigtes Königreich", "Vereinigte Staaten", "Reino Unido", "Estados Unidos", "Países Bajos",
]
REGION_CODES = ("UK GB US USA UAE "  # plus US states and Canadian provinces, as in "Austin, TX"
                "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM "
                "NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC AB BC MB NB NL NS ON PE QC SK").split()
_PLACES = "|".join(sorted(map(re.escape, COUNTRY_NAMES), key=len, reverse=True))
LOCATION = re.compile("(?<!\\w)[A-ZÀ-Ý][\\w'\\u2019.-]*(?:[ -][\\w'\\u2019.-]+){0,3},\\s*"
                      f"(?:(?i:{_PLACES})|{'|'.join(REGION_CODES)})(?![\\w-])")
PARTICLES = {"van", "der", "den", "de", "del", "della", "von", "da", "di", "du", "la", "le", "bin", "binti",
             "al", "el", "ben", "dos", "das", "y"}
NOT_A_NAME = re.compile(r"\b(?:cv|curriculum|vitae|r[ée]sum[ée]|lebenslauf|profile|contact)\b", re.I)

FOLDS = [  # UK -> US spelling, applied to the CV text and the synonyms alike
    (re.compile(r"(?<=\w\w)is(e|ed|es|ing|ation|ations)\b"), r"iz\1"),   # optimise, organisation
    (re.compile(r"(?<=\w\w)ys(e|ed|es|ing)\b"), r"yz\1"),                # analyse
    (re.compile(r"(?<=\w\w\w)our(s|ed|ing)?\b"), r"or\1"),               # colour, behaviour (not hour, your)
    (re.compile(r"(?<=\w\w)([bt])re(s?)\b"), r"\1er\2"),                 # fibre, centre, metre
    (re.compile(r"(?<=e)ll(ed|ing|er|ers)\b"), r"l\1"),                  # modelling, travelled
    (re.compile(r"programme(?=s?\b)"), "program"),
    (re.compile(r"\b(defen|licen|offen)ce"), r"\1se"),
]


def fold(text):
    """Lowercase, strip accents, map UK to US spelling and collapse whitespace.

    Applied to both sides of a keyword match, so 'Optimisation' finds 'optimization' and
    'expérience' finds 'experience'.
    """
    text = unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", text).lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    for pat, rep in FOLDS:
        text = pat.sub(rep, text)
    return " ".join(text.split())


EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"\+?\d[\d\s().-]{6,}\d")
LINK = re.compile(r"linkedin\.com/|github\.com/|https?://|www\.", re.I)
CONTACT_WEIGHTS = {"email": 5, "phone": 3, "international_phone": 2, "link": 2.5, "location": 2.5}
COLS = ["total", "parse", "keywords", "contact", "sections", "order", "dates", "placement", "length", "penalty", "words"]


def _synonym_pattern(syn):
    """Short synonyms (<= 4 chars) match whole words, plural allowed; longer ones match word starts."""
    syn = fold(syn)
    esc = re.escape(syn)
    return r"(?<!\w)" + esc + r"s?(?!\w)" if len(syn) <= 4 else r"(?<!\w)" + esc


def keyword_hits(text, keywords):
    low = fold(text)  # line breaks become spaces
    return {label: any(re.search(_synonym_pattern(s), low) for s in syns)
            for label, syns in keywords.items()}


LIST_ONLY = {"header", "profile", "skills", "languages", "interests"}  # places that claim, not show


def keyword_places(text, keywords):
    """{label: set of sections where a synonym matches}. Lines before the first heading are 'header'."""
    blocks, current = {}, "header"
    for line in text.splitlines():
        key = heading_key(line)
        if key:
            current = key
            continue
        blocks.setdefault(current, []).append(line)
    places = {label: set() for label in keywords}
    for section, lines in blocks.items():
        for label, hit in keyword_hits("\n".join(lines), keywords).items():
            if hit:
                places[label].add(section)
    return places


def load_keywords(path):
    """Read and check a keyword file. Returns (keywords, advert, required).

    Format: {"advert": "label", "keywords": {"label": ["synonym", ...]}, "required": ["label", ...]}.
    "required" is optional: required labels count double and are reported first.
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        raise ValueError(f"{path}: not valid JSON ({err})") from None
    kw = data.get("keywords") if isinstance(data, dict) else None
    if not isinstance(kw, dict) or not kw:
        raise ValueError(f'{path}: needs a non-empty "keywords" object: {{"label": ["synonym", ...]}}')
    for label, syns in kw.items():
        if not isinstance(syns, list) or not syns or not all(isinstance(s, str) and s.strip() for s in syns):
            raise ValueError(f'{path}: keyword "{label}" needs a list of synonym strings, e.g. ["{label.lower()}"]')
    required = data.get("required", [])
    if not isinstance(required, list) or any(r not in kw for r in required):
        unknown = [r for r in required if r not in kw] if isinstance(required, list) else required
        raise ValueError(f'{path}: "required" must list keyword labels; unknown: {unknown}')
    return kw, data.get("advert"), tuple(required)


def heading_key(line):
    """Section key for a heading line, 'other' for an unknown ALL-CAPS heading, else None.

    A heading starts with a capital: a lowercase line such as "negotiation skills" is a wrapped
    fragment of the line above, not a Skills heading.
    """
    s = line.strip()
    if s.endswith(":"):
        s = s[:-1].rstrip()  # "Skills:" is a heading; "Skills: Python, SQL" (colon inside) is a label line
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


def find_location(text):
    """'City, Country' (or US/Canadian 'City, ST') in the first five non-empty lines, else None."""
    head = "\n".join([line for line in text.splitlines() if line.strip()][:5])
    m = LOCATION.search(head)
    return m.group(0) if m else None


def first_line_is_name(text):
    """Whether the first non-empty line looks like a person's name: ATS take it as the candidate's name."""
    first = next((line.strip() for line in text.splitlines() if line.strip()), "")
    words = first.split()
    return (1 <= len(words) <= 5 and not re.search(r"[\d@/|·•,:()]", first) and not NOT_A_NAME.search(first)
            and not ROLE_BLOCKLIST.search(first)
            and all(w[0].isupper() or w.lower() in PARTICLES for w in words))


def contact_checks(text):
    phones = _phones(text)
    return {"email": bool(EMAIL.search(text)), "phone": bool(phones),
            "international_phone": any(p.startswith("+") for p in phones), "link": bool(LINK.search(text)),
            "location": find_location(text) is not None}


def score_text(text, pages, *, keywords=None, expected_dates=1, order_consistent=True, max_pages=2, required=()):
    contact = contact_checks(text)
    seq = section_sequence(text)
    missing_sections = [k for k in REQUIRED if k not in seq]
    matches = list(RANGE.finditer(text))
    ranges = [m.group(1) for m in matches]
    monthly = [m for m in matches  # both ends month-precise (or "Present")
               if not YEAR_ONLY.fullmatch(m.group(1).strip()) and not YEAR_ONLY.fullmatch(m.group(2).strip())]
    ok, misplaced = date_placement(text)
    words = len(re.findall(r"\w+", UNREADABLE.sub(" ", text)))
    garbled = GARBLED.findall(text)
    unreadable = len(UNREADABLE.findall(text))
    r = {
        "contact": sum(CONTACT_WEIGHTS[k] for k, v in contact.items() if v),
        "sections": round(15 * (len(REQUIRED) - len(missing_sections)) / len(REQUIRED), 1),
        "order": (10 if len(seq) >= 2 else 5) if order_consistent else 0,
        "dates": round(5 * min(1, len(ranges) / max(expected_dates, 1)) + 5 * len(monthly) / len(ranges), 1) if ranges else 0,
        "placement": round(10 * ok / (ok + len(misplaced)), 1) if ok + len(misplaced) else 0,
        "length": (2.5 if pages is None or pages <= max_pages else 0) + (2.5 if 300 <= words <= 900 else 0),
        "penalty": min(3 * len(garbled) + min(unreadable, 10), 15),
        "words": words, "pages": pages, "garbled": garbled, "unreadable": unreadable, "sequence": seq,
        "missing_sections": missing_sections, "misplaced_dates": misplaced,
        "missing_contact": [k for k, v in contact.items() if not v],
        "name_line": first_line_is_name(text),
        "first_line": next((line.strip() for line in text.splitlines() if line.strip()), ""),
    }
    r["parse"] = round(max(0.0, r["contact"] + r["sections"] + r["order"] + r["dates"]
                           + r["placement"] + r["length"] - r["penalty"]), 1)
    if keywords:
        hits = keyword_hits(text, keywords)
        weight = {k: 2 if k in required else 1 for k in hits}
        r["keywords"] = round(35 * sum(weight[k] for k, found in hits.items() if found) / sum(weight.values()), 1)
        r["total"] = round(r["parse"] + r["keywords"], 1)
        r["missing_keywords"] = [k for k, v in hits.items() if not v]
        places = keyword_places(text, keywords)
        r["listed_only_keywords"] = [k for k, found in hits.items() if found and places[k] <= LIST_ONLY]
    else:
        r["keywords"] = r["total"] = None
        r["missing_keywords"] = []
        r["listed_only_keywords"] = []
    r["required"] = [k for k in required if keywords and k in keywords]
    r["missing_required"] = [k for k in r["missing_keywords"] if k in required]
    return r


def score_cv(path, keywords=None, max_pages=2, required=()):
    texts, pages = extract_all(path, pdf_hook=pdf_findings)
    texts = normalise(texts)  # idempotent; keeps extract_all's ligature counts
    expected = max(len(RANGE.findall(t)) for t in texts.values()) or 1
    consistent = len({tuple(section_sequence(t)) for t in texts.values()}) == 1
    rows = {n: score_text(t, pages, keywords=keywords, expected_dates=expected,
                          order_consistent=consistent, max_pages=max_pages, required=required) for n, t in texts.items()}
    for n, r in rows.items():
        r["ligatures"] = texts.ligatures.get(n, 0)
        r["layout"] = list(texts.pdf_findings)
    if str(path).lower().endswith(".docx"):
        hf, boxed = docx_header_footer_text(path), docx_textbox_text(path)
        for r in rows.values():
            if hf:
                r["header_footer_text"] = hf
            if boxed:
                r["textbox_text"] = boxed
    return rows


def table(title, rows):
    out = [f"### {title}", "| parser | " + " | ".join(COLS) + " |", "|---|" + "---|" * len(COLS)]
    for name, r in rows.items():
        out.append(f"| {name} | " + " | ".join("—" if r[c] is None else str(r[c]) for c in COLS) + " |")
    return "\n".join(out)


def row_messages(r):
    """Problem messages for one parser's row; problems() groups identical ones across parsers."""
    if r["missing_sections"]:
        yield f"section headings not recognised: {', '.join(r['missing_sections'])}"
    if r["garbled"]:
        yield f"letter-spaced text read as separate letters: {r['garbled'][:3]}"
    if r.get("unreadable"):
        yield (f"{r['unreadable']} unreadable glyph{'s' if r['unreadable'] != 1 else ''} (icon-font symbols, or a font with no text map): "
               "use words ('Email:', 'Phone:') instead of icons and standard fonts")
    if r["misplaced_dates"]:
        yield f"dates landed under the wrong section: {r['misplaced_dates']}"
    if r["missing_contact"]:
        yield f"contact items not found: {', '.join(r['missing_contact'])}"
    if not r["name_line"] and r["words"] >= MIN_WORDS:
        yield f"first line isn't a name ({r['first_line'][:40]!r}): ATS read the first line as the candidate's name"
    if r.get("ligatures"):
        yield (f"extracted {r['ligatures']} ligature glyph(s) (e.g. one glyph for 'fi'); "
               "add font-variant-ligatures: none")


def _who(names, rows):
    return "all parsers" if len(rows) > 1 and len(names) == len(rows) else ", ".join(names)


def keyword_problems(rows):
    """'not found' lines for keywords every parser missed; 'some parsers miss' for the rest."""
    missed = {}
    for name, r in rows.items():
        for label in r["missing_keywords"]:
            missed.setdefault(label, []).append(name)
    everywhere = [k for k, names in missed.items() if len(names) == len(rows)]
    partly = [f"{k} ({', '.join(names)})" for k, names in missed.items() if len(names) < len(rows)]
    out = []
    required = set(next(iter(rows.values())).get("required", []))
    if [k for k in everywhere if k in required]:
        out.append("- required advert keywords not found: " + ", ".join(k for k in everywhere if k in required))
    if [k for k in everywhere if k not in required]:
        out.append("- advert keywords not found: " + ", ".join(k for k in everywhere if k not in required))
    if partly:
        out.append("- advert keywords some parsers miss (a layout problem, not a gap): " + ", ".join(partly))
    listed = [k for k in rows[next(iter(rows))]["listed_only_keywords"]
              if all(k in r["listed_only_keywords"] for r in rows.values())]
    if listed:
        out.append("- advert keywords only in the header, profile or skills list (add a bullet showing where each "
                   "was used, if the person confirms one): " + ", ".join(listed))
    return out


def problems(rows):
    """Problem lines for a {parser: row} table.

    A message several parsers share prints once, followed by the parsers that hit it ("all parsers"
    when every parser did), so the list stays short enough to report in full.
    """
    empty = [name for name, r in rows.items() if r["words"] < MIN_WORDS]
    out = [f"- {NO_TEXT} ({', '.join(empty)})"] if empty else []
    out += [f"- {finding}" for finding in next(iter(rows.values())).get("layout", [])]
    grouped = {}
    for name, r in rows.items():
        for msg in row_messages(r):
            grouped.setdefault(msg, []).append(name)
    out += [f"- {msg} ({_who(names, rows)})" for msg, names in grouped.items()]
    if any(r["order"] == 0 for r in rows.values()):
        seqs = {}
        for name, r in rows.items():
            seqs.setdefault(tuple(r["sequence"]), []).append(name)
        out.append("- parsers disagree on section order: "
                   + "; ".join(f"{', '.join(names)} {list(seq)}" for seq, names in seqs.items()))
    first = next(iter(rows.values()))
    if first.get("header_footer_text"):
        out.append(f"- Word header/footer holds text many ATS skip: {first['header_footer_text']!r}")
    if first.get("textbox_text"):
        out.append(f"- Word text boxes hold text many ATS skip: {first['textbox_text']!r}")
    out += keyword_problems(rows)
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
    keywords, advert, required = None, None, ()
    if a.keywords:
        keywords, advert, required = load_keywords(a.keywords)
    report = {"cv": score_cv(a.cv, keywords, a.max_pages, required)}
    if a.baseline:
        report["baseline"] = score_cv(a.baseline, keywords, a.max_pages, required)
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
