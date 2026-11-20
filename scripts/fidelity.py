#!/usr/bin/env python3
"""Check a rewritten CV against the original for facts the rewrite added.

Lists what NEW has that ORIGINAL doesn't, as items to confirm with the person:
  keyword:<label>    an advert keyword NEW matches and ORIGINAL doesn't (needs --keywords)
  contact:<item>     a contact item NEW has and ORIGINAL doesn't, or has with a different value
                     (email, phone, link, location; international_phone = a +CC form ORIGINAL lacks)
  number:<n>         a number, %, amount or threshold ("3+") not in ORIGINAL
  date:<YYYY-MM>     a month-year date not in ORIGINAL (a years-only date made precise), or not on
                     the matching ORIGINAL line
  date:<YYYY>        a year not in ORIGINAL, or not on the matching ORIGINAL line (an entry re-dated)
  term:<TERM>        an acronym, CamelCase name or code (SQL, HubSpot, GA4) not in ORIGINAL
  supporting-verbs   a helped/assisted/supported/... line kept in NEW without its supporting verb
Rewording a number ("40,000" -> "40k") also shows as new: confirm it's the same figure.
Exit code 1 while any item is unconfirmed. Pass items the person confirmed to --confirmed, exactly
as printed and comma-separated; take everything else out of the CV.

Usage: cvats fidelity ORIGINAL NEW [--keywords KW.json] [--confirmed "number:3+,contact:location"]
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from cvlib import cli, docx_header_footer_text, extract_all  # noqa: E402
from score import (DATE, EMAIL, MONTH, PHONE, contact_checks, find_location, fold, heading_key,  # noqa: E402
                   keyword_hits, load_keywords)

CONTACT_ITEMS = ("email", "phone", "international_phone", "link", "location")
# Verb forms only: a bare stem would also match job titles and nouns ("Sales Assistant",
# "IT Support Analyst", "First Aid", "Contributor"), and a title moved to its own line would
# then look like an upgraded "Helped..." bullet.
SUPPORTING = re.compile(
    r"(?<!\w)(?:help(?:ed|ing|s)?|assist(?:ed|ing|s)|support(?:ed|ing|s)|contribut(?:ed|ing|es?)"
    r"|particip(?:ated|ating|ates?|é|ée|er)|collaborat(?:ed|ing|es?)|aid(?:ed|ing)"
    r"|aidé|aidée|aider|contribué|contribuée|collaboré|collaborée|assisté|assistée)(?!\w)", re.I)
NUMBER = re.compile(r"(?<![\w.])[£$€]?\d+(?:[,.\u202f\u00a0 ]\d{3})*(?:[.,]\d+)?(?:\s?(?:%|\+|k\b|m\b|bn\b))?",
                    re.I)
DATE_RE = re.compile(rf"(?<![\w.,£$€])(?:{DATE})(?!\w)", re.I)
YEAR = re.compile(r"(?:19|20)\d{2}")
YEAR_TOKEN = re.compile(r"(?<![\w£$€.,])(?:19[5-9]\d|20\d\d|2100)(?![\w%]|[.,]\d)")
LINK_TOKEN = re.compile(r"\S*(?:linkedin\.com|github\.com|https?://|www\.)\S*", re.I)
WORD = re.compile(r"[^\W\d_]{3,}")
STOP = {"and", "the", "for", "with", "from", "into", "onto", "our", "their", "its", "was", "were", "per"}
MONTH_YEAR = re.compile(rf"(?<!\w)({MONTH})\s+((?:19|20)\d{{2}})(?!\d)"
                        rf"|(?<![\d.])(\d{{1,2}})[./]((?:19|20)\d{{2}})(?!\d)"
                        rf"|(?<!\d)((?:19|20)\d{{2}})-(0[1-9]|1[0-2])(?!\d)", re.I)
MONTH_KEYS = {"jan": 1, "ene": 1, "feb": 2, "fev": 2, "mar": 3, "mae": 3, "apr": 4, "avr": 4, "abr": 4, "may": 5,
              "mai": 5, "jun": 6, "jul": 7, "aug": 8, "aou": 8, "ago": 8, "sep": 9, "set": 9, "oct": 10,
              "okt": 10, "nov": 11, "dec": 12, "dez": 12, "dic": 12}
TOKEN = re.compile(r"[^\W\d_](?:[^\W_]|[+#&])*")  # Unicode letters: ÉCOLE stays whole


def _strip_contacts(text):
    text = EMAIL.sub(" ", text)
    text = LINK_TOKEN.sub(" ", text)
    return PHONE.sub(lambda m: " " if len(re.sub(r"\D", "", m.group())) >= 9 else m.group(), text)


def numbers(text):
    """Normalised numbers, minus contact details and dates: '40,000' -> '40000', '25 %' -> '25%'."""
    out = set()
    for m in NUMBER.finditer(DATE_RE.sub(" ", _strip_contacts(text))):
        token = re.sub(r"[,.](?=\d{3}\b)", "", re.sub(r"\s", "", m.group()).lower())
        if not YEAR.fullmatch(token):
            out.add(token)
    return out


def _month(word):
    w = fold(word).rstrip(".")
    if w[:4] in ("juin", "juil"):
        return 6 if w[:4] == "juin" else 7
    return MONTH_KEYS.get(w[:3])


def month_years(text):
    """{'YYYY-MM'} for every month-year date: 'Mar 2021', 'mars 2021', '03/2021', '2021-03'."""
    out = set()
    for m in MONTH_YEAR.finditer(text):
        if m.group(1):
            month, year = _month(m.group(1)), m.group(2)
        elif m.group(3):
            month, year = int(m.group(3)), m.group(4)
        else:
            month, year = int(m.group(6)), m.group(5)
        if month and 1 <= month <= 12:
            out.add(f"{year}-{month:02d}")
    return out


def years(text):
    """{'YYYY'} for every year 1950-2100 standing alone or in a date, minus contact details and amounts."""
    return set(YEAR_TOKEN.findall(_strip_contacts(text)))


def emails(text):
    return {e.lower() for e in EMAIL.findall(text)}


def phones(text):
    """Phone numbers as digit strings, '+' kept for international ones ('0044' counts as '+44')."""
    out = set()
    for m in PHONE.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if len(digits) >= 9:
            intl = m.group().lstrip().startswith("+") or digits.startswith("00")
            out.add("+" + digits.removeprefix("00") if intl else digits)
    return out


def same_phone(a, b):
    """Equal digits, or one is '+CC' + the other without its national leading 0."""
    if a.lstrip("+") == b.lstrip("+"):
        return True
    intl, national = (a, b) if a.startswith("+") else (b, a)
    if not intl.startswith("+") or national.startswith("+") or not national.startswith("0"):
        return False
    rest = national[1:]
    return intl.endswith(rest) and 1 <= len(intl) - 1 - len(rest) <= 3


def links(text):
    """Links lower-cased, without scheme, 'www.' or trailing slash/punctuation."""
    out = set()
    for t in LINK_TOKEN.findall(text):
        t = re.sub(r"^(?:https?://)?(?:www\.)?", "", t.lower()).rstrip("/.,;:)|")
        out.add(t)
    return out


def words(line):
    return {w for w in (fold(x) for x in WORD.findall(line)) if w not in STOP}


def best_line(line, lines, threshold):
    """The line in lines whose content words overlap line's most (Jaccard >= threshold), else None."""
    mine = words(line)
    if len(mine) < 3:
        return None
    score, best = max(((len(mine & words(o)) / len(mine | words(o)), o) for o in lines), default=(0, None))
    return best if score >= threshold else None


def entry_dates(orig_lines, new_text):
    """{date item: original line} for dates on a NEW line that its matching ORIGINAL line doesn't have."""
    out = {}
    for line in new_text.splitlines():
        ys, ms = years(line), month_years(line)
        if not ys:
            continue
        match = best_line(line, [o for o in orig_lines if years(o)], 0.6)
        if match is None:
            continue
        out.update({f"date:{y}": match for y in ys - years(match)})
        if month_years(match):
            out.update({f"date:{d}": match for d in ms - month_years(match)})
    return out


def supporting_upgrades(orig_lines, new_lines):
    """Original lines with a supporting verb whose content NEW keeps without any supporting verb."""
    out = []
    for line in orig_lines:
        if not SUPPORTING.search(line):
            continue
        content = words(SUPPORTING.sub(" ", line))
        if len(content) < 2:
            continue
        kept = [n for n in new_lines if len(content & words(n)) >= 0.75 * len(content)]
        if kept and not any(SUPPORTING.search(n) for n in kept):
            out.append(line.strip(" •-*\t"))
    return out


def terms(text):
    """Acronyms, CamelCase names and letter-digit codes (SQL, HubSpot, GA4), skipping section headings."""
    out = set()
    for line in text.splitlines():
        if heading_key(line) not in (None, "other"):
            continue
        for t in TOKEN.findall(line):
            if (sum(c.isupper() for c in t) >= 2 or any(a.islower() and b.isupper() for a, b in zip(t, t[1:]))
                    or (len(t) >= 2 and re.search(r"\d", t))):
                out.add(t)
    return out


def cv_texts(path):
    """extract_all's {parser: text}, plus a .docx's Word header/footer text (where contact details often sit)."""
    texts = dict(extract_all(path)[0])
    if Path(path).suffix.lower() == ".docx":
        header = docx_header_footer_text(path)
        if header.strip():
            texts["word-header-footer"] = header
    return texts



def findings(orig_texts, new_texts, keywords=None):
    """[(item, detail)] for facts in the new CV that the original doesn't have.

    Each argument is {parser: text}. The original counts as saying something if any of its parsers
    read it; the new CV is judged by its first parser.
    """
    orig_all = "\n".join(orig_texts.values())
    orig_first, new = next(iter(orig_texts.values())), next(iter(new_texts.values()))
    items = []
    if keywords:
        before, after = keyword_hits(orig_all, keywords), keyword_hits(new, keywords)
        items += [(f"keyword:{k}", "advert keyword the original doesn't match") for k in keywords
                  if after[k] and not before[k]]
    had = {k: any(contact_checks(t)[k] for t in orig_texts.values()) for k in CONTACT_ITEMS}
    now = contact_checks(new)
    location = find_location(new)
    old_phones = phones(orig_all)
    changed = {
        "email": sorted(emails(new) - emails(orig_all)),
        "phone": sorted(p for p in phones(new) if not any(same_phone(p, o) for o in old_phones)),
        "link": sorted(links(new) - links(orig_all)),
        "international_phone": [],
        "location": ([location] if location and (not had["location"] or fold(location.split(",")[0])
                                                 not in fold(orig_all)) else []),
    }
    for k in CONTACT_ITEMS:
        if k == "location" and changed[k]:
            items.append((f"contact:{k}", repr(location)))
        elif now[k] and not had[k]:
            items.append((f"contact:{k}", "not in the original"))
        elif changed[k]:
            items.append((f"contact:{k}", "differs from the original: " + ", ".join(changed[k])))
    items += [(f"number:{n}", "") for n in sorted(numbers(new) - numbers(orig_all))]
    orig_lines = list(dict.fromkeys(line for t in orig_texts.values() for line in t.splitlines() if line.strip()))
    dates = {f"date:{d}": "month-year date not in the original" for d in month_years(new) - month_years(orig_all)}
    dates.update({f"date:{y}": "year not in the original" for y in years(new) - years(orig_all)})
    for item, line in entry_dates(orig_lines, new).items():
        dates.setdefault(item, f"not on the matching original line: {line.strip()!r}")
    precise = {d[5:9] for d in dates if len(d) == 12}  # date:YYYY-MM already names the year
    items += sorted((d, why) for d, why in dates.items() if not (len(d) == 9 and d[5:] in precise))
    body = _strip_contacts(new).replace(location, " ") if location else _strip_contacts(new)
    old_words = {fold(w) for w in re.findall(r"[\w+#&]+", orig_all)}
    items += [(f"term:{t}", "") for t in sorted(terms(body)) if fold(t) not in old_words]
    upgraded = supporting_upgrades(orig_first.splitlines(), new.splitlines())
    if upgraded:
        items.append(("supporting-verbs", "kept without its helped/assisted/supported verb: "
                      + "; ".join(repr(u) for u in upgraded)))
    return items


@cli
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("original")
    ap.add_argument("new")
    ap.add_argument("--keywords")
    ap.add_argument("--confirmed", default="", help="comma-separated items the person confirmed, as printed")
    a = ap.parse_args(argv)
    keywords = load_keywords(a.keywords)[0] if a.keywords else None
    confirmed = {c.strip() for c in a.confirmed.split(",") if c.strip()}
    items = findings(cv_texts(a.original), cv_texts(a.new), keywords)
    print("Fidelity check: facts in the new CV that the original doesn't have. "
          "Each needs the person's confirmation, or it comes out.")
    for item, detail in items:
        print(f"- {item}  [{'confirmed' if item in confirmed else 'UNCONFIRMED'}]" + (f"  {detail}" if detail else ""))
    unknown = sorted(confirmed - {item for item, _ in items})
    if unknown:
        print("note: --confirmed items not found (typo?): " + ", ".join(unknown))
    open_items = [item for item, _ in items if item not in confirmed]
    print(f"unconfirmed: {len(open_items)}  confirmed: {len(items) - len(open_items)}")
    return 1 if open_items else 0


if __name__ == "__main__":
    sys.exit(main())
