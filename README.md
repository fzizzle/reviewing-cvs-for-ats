# reviewing-cvs-for-ats

A [Claude Code](https://claude.com/claude-code) skill for reviewing, rewriting, tailoring and ATS-testing CVs and résumés. It works for any industry or country, and takes PDF, Word, HTML or plain text.

It runs a fixed workflow: intake questions, a baseline score, feedback, a keyword file built from a real job advert, a rewrite into an ATS-safe one-page HTML template, and checks after every edit. The main rule is **never invent a fact**. Anything the person hasn't confirmed (a tool, a number, a date, a city) goes on a "gaps to confirm" list, not into the CV.

## What it measures

The `scripts/cvats` toolkit runs locally:

| Command | What it does |
|---|---|
| `score` | A local ATS simulation. It extracts the CV with four PDF parsers (pypdf, pdfminer, pdfplumber, pymupdf) or two Word parsers, and scores parse quality out of 65 and advert keywords out of 35. This is a heuristic, not a commercial ATS score. |
| `layout` | Flags small text, orphan lines, side-by-side columns, right-aligned dates and hidden text. |
| `repeats` | Finds repeated bullet openers and repeated 3-word phrases. |
| `fidelity` | Lists facts in a rewrite that the original didn't have, so each one can be confirmed or removed. |
| `render` | Renders the HTML CV to PDF with headless Chrome. |
| `extract` | Prints what each parser reads from the CV. |

## Install

1. Copy this folder to `~/.claude/skills/reviewing-cvs-for-ats`:
   ```bash
   git clone https://github.com/fzizzle/reviewing-cvs-for-ats ~/.claude/skills/reviewing-cvs-for-ats
   ```
2. Install the requirements:
   - Python 3.10+
   - Google Chrome (or Chromium), for `render`

   The first `cvats` call creates a virtualenv at `~/.cache/cv-ats/venv` and installs the parsers from `scripts/requirements.txt`. Set `CV_ATS_VENV` to put it somewhere else.
3. In Claude Code, ask something like "review my CV" or "tailor my CV to this advert", or type `/reviewing-cvs-for-ats`.

## Use the tools directly

```bash
CVATS=~/.claude/skills/reviewing-cvs-for-ats/scripts/cvats
$CVATS score my_cv.pdf --keywords kw.json
$CVATS layout my_cv.pdf
$CVATS fidelity original.pdf new.pdf
```

See `templates/keywords-example.json` for the keyword file format, and `reference/` for the rubric and the ATS rules.

## Privacy

CVs are personal data. Everything runs locally, and the skill never uploads a CV to an online ATS checker without the person's consent. All test fixtures are fictional, and `tests/test_privacy.py` checks that tracked files contain only fictional phone numbers and `@example.com` addresses.

## Tests

```bash
~/.cache/cv-ats/venv/bin/python -m pytest -q tests
```
