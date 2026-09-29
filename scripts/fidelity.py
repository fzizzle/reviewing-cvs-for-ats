#!/usr/bin/env python3
"""Check a rewritten CV against the original for facts the rewrite added.

Lists what NEW has that ORIGINAL doesn't, as items to confirm with the person:
  keyword:<label>    an advert keyword NEW matches and ORIGINAL doesn't (needs --keywords)
  contact:<item>     a contact item NEW has and ORIGINAL doesn't (location, link, international_phone, ...)
  number:<n>         a number, %, amount or threshold ("3+") not in ORIGINAL
  date:<YYYY-MM>     a month-year date not in ORIGINAL (a years-only date made precise)
  term:<TERM>        an acronym, CamelCase name or code (SQL, HubSpot, GA4) not in ORIGINAL
  supporting-verbs   fewer helped/assisted/supported/contributed/participated/collaborated than ORIGINAL
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
from cvlib import cli, extract_all  # noqa: E402
from score import (DATE, EMAIL, MONTH, PHONE, contact_checks, find_location, fold, heading_key,  # noqa: E402
                   keyword_hits, load_keywords)

CONTACT_ITEMS = ("email", "phone", "international_phone", "link", "location")
SUPPORTING = re.compile(r"(?<!\w)(?:help|assist|support|contribu|particip|collabor|aid)\w*", re.I)
NUMBER = re.compile(r"(?<![\w.])[£$€]?\d+(?:[,.\u202f\u00a0 ]\d{3})*(?:[.,]\d+)?(?:\s?(?:%|\+|k\b|m\b|bn\b))?",
                    re.I)
DATE_RE = re.compile(rf"(?<![\w.,£$€])(?:{DATE})(?!\w)", re.I)
YEAR = re.compile(r"(?:19|20)\d{2}")
MONTH_YEAR = re.compile(rf"(?<!\w)({MONTH})\s+((?:19|20)\d{{2}})(?!\d)"
                        rf"|(?<![\d.])(\d{{1,2}})[./]((?:19|20)\d{{2}})(?!\d)"
                        rf"|(?<!\d)((?:19|20)\d{{2}})-(0[1-9]|1[0-2])(?!\d)", re.I)
MONTH_KEYS = {"jan": 1, "ene": 1, "feb": 2, "fev": 2, "mar": 3, "apr": 4, "avr": 4, "abr": 4, "may": 5,
              "mai": 5, "jun": 6, "jul": 7, "aug": 8, "aou": 8, "ago": 8, "sep": 9, "set": 9, "oct": 10,
              "okt": 10, "nov": 11, "dec": 12, "dez": 12, "dic": 12}
TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9+#&]*")


def _strip_contacts(text):
    text = EMAIL.sub(" ", text)
    text = re.sub(r"\S*(?:linkedin\.com|github\.com|https?://|www\.)\S*", " ", text, flags=re.I)
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


def terms(text):
    """Acronyms, CamelCase names and letter-digit codes (SQL, HubSpot, GA4), skipping heading lines."""
    out = set()
    for line in text.splitlines():
        if heading_key(line):
            continue
        for t in TOKEN.findall(line):
            if (sum(c.isupper() for c in t) >= 2 or re.search(r"[a-z][A-Z]", t)
                    or (len(t) >= 2 and re.search(r"\d", t))):
                out.add(t)
    return out


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
    items += [(f"contact:{k}", repr(location) if k == "location" else "not in the original")
              for k in CONTACT_ITEMS if now[k] and not had[k]]
    items += [(f"number:{n}", "") for n in sorted(numbers(new) - numbers(orig_all))]
    items += [(f"date:{d}", "month-year date not in the original")
              for d in sorted(month_years(new) - month_years(orig_all))]
    body = _strip_contacts(new).replace(location, " ") if location else _strip_contacts(new)
    old_words = {fold(w) for w in re.findall(r"[\w+#&]+", orig_all)}
    items += [(f"term:{t}", "") for t in sorted(terms(body)) if fold(t) not in old_words]
    n_old, n_new = len(SUPPORTING.findall(orig_first)), len(SUPPORTING.findall(new))
    if n_new < n_old:
        items.append(("supporting-verbs", f"original {n_old}, new {n_new}: check no 'helped' became 'led'"))
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
    items = findings(extract_all(a.original)[0], extract_all(a.new)[0], keywords)
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
