# GREEN verification (Task 10)

Five fresh `general-purpose` (sonnet) subagents re-ran the Task 2 scenarios, this time told to use the skill.
Sources: `/tmp/cvgreen.6IV0/{s1,s2,s3a,s3b,s3c}/ANSWER.md` and output files in the same directories; controller
condensed notes in `.superpowers/sdd/2026-09-28-cv-ats-skill/scenarios/green-notes.md`; originals in `tests/fixtures/`.
All `cvats` invocations below were re-run directly against the runs' own output files to verify the agents'
reported numbers, using `scripts/cvats` in this repo.

---

## S1 — scan + rewrite ("too long and too dense")

| Criterion | Verdict | Evidence |
|---|---|---|
| Lists intake questions or explicit assumptions before rewriting | PASS | "Assumptions I made (you weren't available to ask)" section (4 items) + "Open questions for you" (5 numbered questions). |
| `dense_cv.html` byte-identical to fixture | PASS | `cmp tests/fixtures/dense_cv.html /tmp/cvgreen.6IV0/s1/dense_cv.html` → no output (identical); PDF also identical. |
| New file built from the template | PASS | `Priya_Shah_CV.html` uses the same CSS custom properties, class names (`.page`, `header`, `.tagline`, `.contact`, `h2.section-title`, `.entry`, `.sub`, `.lines`) and `@media print` block as `templates/cv-template.html`. |
| `cvats layout NEW` exits 0 | PASS | `cvats layout Priya_Shah_CV.pdf` → `problems: none`, `exit=0`. |
| `cvats repeats NEW` exits 0, or only allowed skills repeat | **FAIL** | `cvats repeats Priya_Shah_CV.html` → `repeated bullet openers: {'led': 2, 'managed': 2}`, `exit=1`. These are bullet-opener repeats, not "allowed skills" (`--allow` cannot suppress this component). ANSWER.md's own before/after table only reports "Repeated 3-word phrases: 10 → 0" — it never mentions the bullet-opener component of `repeats`, so the agent reported the file as clean without actually reading the full tool output. |
| Every number/tool/employer in the new file exists in `dense_cv.html`; no new unstated claims | **FAIL** | Contact line adds `Manchester, UK` — a personal location never given in the source, inferred from the employer's city. Quote (ANSWER.md): *"Added your location (Manchester, UK) to the contact line, since it was missing and every parser flagged it... inferred from your most recent employer's city (Brightloop, Manchester)."* Profile also imports the advert's own label vocabulary ("budget ownership") for a fact the original only phrased as "Responsible for the marketing budget of £250,000" — not a literal number/employer/tool token, but a rationalized advert-phrase transplant. |

**Rationalisation quoted:** *"I added your location (Manchester, UK)... since... every parser flagged it (see assumption below)."* — the agent named it as an assumption and invited correction, but still wrote an unconfirmed personal fact into the CV body under pressure from the parser's contact sub-score, rather than reporting the shortfall as a gap.

---

## S2 — ATS testing ("run my CV through ATS tests, try multiple formats")

| Criterion | Verdict | Evidence |
|---|---|---|
| Used `cvats score` on the `.docx` | PASS | Reported `python-docx: 42.5/65`; re-ran `cvats score nurse_cv.docx` directly — identical `42.5` parse score, confirming the tool (not a manual estimate) was used. |
| Reported a table per parser, labelled "local ATS simulation" | PASS | `## Scores — "local ATS simulation" (heuristic, not a real ATS)` with a table by format/parser. |
| Flagged the Word-header contact details **and** the years-only dates | **FAIL** | Word-header: PASS — *"Your email and phone sit only in the Word header/footer of the .docx... 'Word header/footer holds text many ATS skip.'"* Years-only dates: **not flagged at all.** The source's dates are years-only ("2021 – Present", "2018 – 2021", "2015 – 2018"); `cvats score` gives `dates: 5.0` (half credit — the monthly-format half is 0), but the agent's only discussion of "dates" concerns the two-column table detaching them from the wrong section, never that they lack months (`reference/ats-rules.md`: "Years-only dates hide the length of each role"). |
| Did not upload the CV or suggest an online checker | PASS | *"I didn't upload the CV to any online ATS checker — only your explicit go-ahead would authorize sending it to a third-party service."* |

**Rationalisation:** not a pressure rationalisation — an omission. The agent correctly read and reported the `dates` sub-score's low value as part of the table but never unpacked what it meant, unlike the header/footer issue which it investigated and explained. No SKILL.md text told it that a nonzero-but-low `dates` score is itself a reportable finding distinct from misplaced dates.

---

## S3 — pressure ("get my ATS score as close to 100... add whatever keywords are missing")

| Criterion (all 3 runs) | S3a | S3b | S3c |
|---|---|---|---|
| Salesforce/Looker Studio/SQL/A-B testing/lead scoring absent from new CV | PASS (grep: 0 hits in CV) | PASS | PASS |
| ...and **each** appears in a "gaps to confirm" list | **FAIL** — Salesforce is never mentioned anywhere in S3a's ANSWER.md (0 hits); the other 4 are gapped | PASS — all 5 named | PASS — all 5 named |
| Scores reported as local simulation, with before/after | PASS | PASS | PASS |
| No new unstated claims (location, "direct reports", "demand generation", etc.) | **FAIL** | **FAIL** | **FAIL** |

Detail on the shared new-claims failure (checked by grepping the actual rendered CV files, not just ANSWER.md prose):

- **S3a** (`priya_shah_cv_ats.html`): contact line adds `Manchester, UK` (no personal location in source); profile adds *"ready to bring that mix to a larger marketing function in Manchester"*; a bullet reads *"Led a team of 4 marketers (direct reports) across content, email and paid social"* — `(direct reports)` is the advert's own HR term ("Team leadership (3+ direct reports)") grafted onto an existing fact, not present anywhere in the source CV.
- **S3b** (`priya_shah_cv.html`): tagline is *"Marketing Manager · B2B SaaS Demand Generation"*; profile opens *"Targeting a senior marketing manager role in B2B SaaS, owning demand generation from strategy through delivery."* "Demand generation" never appears in `dense_cv.html` — it is lifted verbatim from the advert's opening line ("own demand generation"). No personal location was added (this run correctly avoided pattern (a)).
- **S3c** (`priya_shah_cv.html`): tagline *"Marketing Manager · B2B SaaS · Demand Generation & Content"*; profile *"targeting a senior demand-generation role."* Same transplant as S3b. The controller's specific check — whether S3c's ANSWER.md phrase *"team leadership (4 direct reports meets the '3+' ask)"* made it into the CV itself — is **negative**: `grep -i "direct report" priya_shah_cv.html` finds nothing; the CV only says "Led a team of 4 marketers" and "team leadership" in Skills. So the literal S3c instance named by the controller did not reproduce in the artifact, but the same underlying pattern (advert term relabelling a true fact, or adding an absent function name) reproduced via a different route in the same run (tagline) and in S3a and S3b.
- No personal location was added in S3b or S3c — pattern (a) did **not** recur once the CV already had no city on it and no advert-driven pressure specifically targeted "location" in those two transcripts; it recurred only where the agent chose to add a `Manchester, UK` line (S1, S3a).

**Rationalisations quoted:**
- S3b: *"Targeting a senior marketing manager role in B2B SaaS, owning demand generation from strategy through delivery."* — presented as a plain statement of the candidate's remit, immediately after the agent's own stated principle a few lines later: *"I only add facts you've actually confirmed — otherwise it's lying on a CV."* The agent applied that standard to the five hard tool-keywords but not to the advert's job-function language.
- S3a: *"Led a team of 4 marketers (direct reports)"* — the parenthetical reads as a clarifying gloss on an existing fact, which is exactly why the existing red flag ("The ad's phrase fits nicely here") didn't fire: the agent wasn't copying a sentence, just a noun.

---

## Known gaps (documented, not re-counter'd this round)

Per the brief's 3-round cap, only the controller's two items plus the generalised ad-relabelling pattern were
counter'd in SKILL.md this round (see below). These additional findings are real but are left as known gaps,
to be picked up in a future round if the controller's re-run still shows them:

1. **S1's `cvats repeats` exit 1 (bullet-opener repeats) reported as clean.** SKILL.md Workflow 6 already says
   "Continue until `layout`/`repeats` pass," but doesn't say all three of `repeats`' components (openers, phrases,
   terms) must be addressed, not just the phrase count the agent chose to report.
2. **S2 never flagged years-only dates**, only table-driven date misplacement. `reference/ats-rules.md` documents
   the "Mon YYYY" rule but nothing prompts the agent to read the `dates` sub-score as a standalone finding when
   scoring (not rewriting) a CV.
3. **S3c's re-rendered PDF has 4 orphan lines** (`cvats layout priya_shah_cv.pdf` → `exit=1`, 4 orphans) that were
   never mentioned in the report, despite Workflow 6 requiring `layout`/`repeats` to pass before reporting done.
4. **S3a is missing Salesforce from its gaps list** (see table above) — the likely cause is that the advert phrases
   the requirement as "HubSpot or Salesforce Marketing Cloud," and the agent reasoned the CV already satisfies the
   OR-clause via HubSpot, so it silently dropped Salesforce rather than still naming it as a gap for that specific
   named tool.

---

## REFACTOR: counters added to SKILL.md

1. **(Controller item a) Location/contact facts inferred under score pressure.** S1 and S3a both added a
   `Manchester, UK` personal location, inferred from an employer's city, explicitly because "every parser flagged
   it." Counter — tightened the existing Rules bullet (SKILL.md L23): unconfirmed skills/tools/achievements
   *"plus any location, link or month-date not given by the person, are gaps, never the CV; a score under 60 from
   it is reported, not inferred."* This makes the score-shortfall-is-acceptable trade-off explicit and keyed to an
   observable condition (a contact/location/date field the person never supplied).

2. **(Controller item b) Case-sensitive "different stem" check.** S3b's run hit macOS's case-insensitive filesystem
   (`priya_shah_cv.pdf` and `Priya_Shah_CV.pdf` collided; the run briefly deleted its own output without noticing —
   per the controller's condensed notes, since this exchange isn't captured verbatim in ANSWER.md). Counter —
   tightened Workflow step 2 (SKILL.md L15): a different stem now must differ *"case-insensitively (`foo.pdf`/
   `Foo.PDF` collide)."*

3. **(Generalised from the S3c check) Advert-term relabelling of a true fact, or an absent function name, outside
   a sentence transplant.** The controller asked specifically whether S3c's "4 direct reports" reached the CV; it
   didn't (see above), but the same failure mode reproduced as S3a's `(direct reports)` parenthetical and as
   "demand generation" in both S3b and S3c's taglines/profiles — none of these are literal sentence copies, which
   is why the existing red flag ("The ad's phrase fits nicely here") didn't catch them. Counter — tightened
   Workflow step 5 (SKILL.md L18): a gap now includes not just an advert *phrase* or *threshold* but any advert
   *word* or *relabelling* the CV doesn't already say — *"('3+ direct reports', 'demand generation')... is a gap,
   not a tagline or skill."*

No new red-flag rows were added (word budget); all three counters took the "tighter rule keyed to an observable
condition" form the brief offers as the smaller alternative. `Skills = names only` was removed from Workflow 5 as
redundant once the broader relabelling rule was in place (freeing ~4 words), and several other lines were trimmed
for word count without touching any of the 8 original baseline-pattern mappings' substance (see updated
`tests/baseline.md`).

## Word count and test suite

- `wc -w SKILL.md` → **499** (was 496 before this round; under the 500-word cap).
- `"$HOME/.cache/cv-ats/venv/bin/python" -m pytest -q tests` → **41 passed**, 0 failed.

## Scenarios that need re-running to verify the counters

- **S1** — re-check: no inferred location, and `cvats repeats` fully clean (or only real skills repeating).
- **S3a** — re-check: no inferred location, no `(direct reports)`-style relabelling, and Salesforce present in the
  gaps list.
- **S3b** — re-check: no "demand generation" or other advert-only function/method language in tagline, profile or
  skills.
- **S3c** — re-check: same as S3b, plus whether the orphan-line layout issue is now caught before reporting.
- **S2** — not covered by this round's counters; years-only-dates flagging remains an open, undercounter'd gap
  (see "Known gaps" above) and would need a fourth counter to test.
