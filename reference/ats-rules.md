# ATS rules (layout) and how to read the local score

| Rule | Why |
|---|---|
| Single column; no tables or text boxes for layout | Parsers read tables and columns in unpredictable order |
| Contact details in the body, not a Word header/footer | Many ATS skip headers and footers (`cvats score` warns) |
| Standard headings: Profile, Experience, Education, Projects, Skills, Languages | Parsers map sections by name |
| Headings as real text with letter-spacing ≤ 0.04em | Wider spacing extracts as "E X P E R I E N C E" |
| `font-variant-ligatures: none` on `body` (the template has it) | Some fonts print "fi"/"fl" as one glyph, so a parser reads "Proﬁle", not "Profile" (`cvats score` flags it) |
| No monospace fonts for headings (e.g. IBM Plex Mono, Consolas, Courier) | Some parsers split long monospaced words by glyph metrics alone ("E XPE RIE NCE"), whatever the letter-spacing — check with `cvats extract` |
| Dates inline with the employer line, not in a right-aligned column | Some parsers lift right-aligned text out as a block; dates land under a later section |
| Dates as "Mon YYYY – Mon YYYY" / "Present" | Years-only dates hide the length of each role |
| Job title on its own line, then "Employer · City · Dates" | Keeps title, employer and dates together |
| Keywords in bullets as well as in Skills | Context beats keyword lists |
| Text-based PDF (from HTML or Word), never scanned images | Images have no text to parse |
| File name `Firstname_Lastname_CV.pdf` | Recruiters search by name |

## Building `kw.json`
Format: `{"advert": "short label", "keywords": {"label": ["synonym", ...], ...}}` — see `templates/keywords-example.json`. Use 12–25 labels, one per distinct advert requirement. Keep every named tool or technology as its own label, even where the advert offers alternatives ("HubSpot or Salesforce Marketing Cloud") — an OR-merged label lets an unconfirmed tool hide behind a confirmed one in `missing_keywords` and skip the gaps list. Synonyms match case-insensitively, across line breaks: short synonyms (≤4 chars) match whole words, plural allowed ("api" finds "APIs", "ai" misses "Aim"); longer ones match word starts ("manufactur" finds "manufacturing"). So list 'leadership' separately from 'lead'.

## Reading `cvats score`
- It's a local heuristic. Always say "local ATS simulation", never "your ATS score".
- Parse /65 is layout health: aim for ≥ 60 on every parser. A parser that disagrees with the others is the finding, so read `problems`.
- Keywords /35 depend on the advert file. Write the file from the advert's requirements before scoring, then freeze it.
- Don't chase 100. Missing keywords the person hasn't confirmed go in a "gaps to confirm" list, never into the CV.
- Check scorer surprises by reading the extracted text (`cvats extract CV --out dir`) before trusting or dismissing them.
- Don't upload a CV to online ATS checkers unless the person explicitly agrees. It's personal data sent to a third party.

## Known tool limits
- `cvats layout` misses orphan lines (a wrapped line holding 1–2 words) when line-height exceeds ~1.55 (its wrap test assumes line gap ≤ 1.55 × font size) — above that, Read the rendered PDF and check by eye.
- `cvats repeats` builds 3-word phrases after dropping stopwords, months and bare numbers, across line and section breaks, so a flagged phrase may not be a literal quote — find it in the source before rewriting. `--allow` hides a phrase only when all three of its words are allowed. Its stopword and month lists are English/French only, so in other languages expect phrases padded with words like "und", "der" or "para" — judge those by eye.
- `cvats score` knows section headings, month names and "present" words in English, French, German and Spanish only, plus numeric dates ("03.2019", "3/2019", ISO "2019-03"). For a CV in another language, read the extracted text instead of trusting the sections/dates sub-scores.
- `cvats score` treats a short line naming a section as a heading only when it starts with a capital, but a wrapped fragment that starts with one ("SQL skills" alone on a line) can still be misread as a heading — if `problems` shows dates under the wrong section, check the extracted text.
