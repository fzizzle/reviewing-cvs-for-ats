---
name: reviewing-cvs-for-ats
description: Use when someone asks to review, shorten, tighten, rewrite, tailor or ATS-test a CV or résumé, says it is too long or dense, asks why it gets no interviews, or wants ATS scores — any industry or country, from PDF, Word, HTML or pasted text.
---

# Reviewing CVs for ATS

## Overview
Loop: scan, feedback, rewrite, run the local ATS tests; stop when checks pass. Never invent a fact or attach an advert's wording to experience it doesn't match. Scripts in `scripts/` measure and render everything — don't write your own or install other tools (e.g. `brew`).

`CVATS=~/.claude/skills/reviewing-cvs-for-ats/scripts/cvats`. First run builds a venv. Commands: `render`, `extract`, `score`, `repeats`, `layout` (`--help` each; tool limits: [reference/ats-rules.md](reference/ats-rules.md)).

## Workflow
1. **Intake** ([reference/intake.md](reference/intake.md)): role, industry, job type/timing, country, an advert — don't rewrite blind. Can't ask? State each as an explicit assumption, not a silent decision.
2. **Baseline, never touch the original.** Copy to a working filename first; save pasted text as `.txt`. Run `score`, `layout`, `repeats`, keep the numbers. Unsure? `cmp original working`.
3. **Feedback** ([reference/feedback-rubric.md](reference/feedback-rubric.md)): top 3–5 issues, then open questions.
4. **Keyword file.** Write the advert's requirements to `kw.json` (format: `templates/keywords-example.json`, 12–25 labels with synonyms); freeze it.
5. **Rewrite** into a copy of `templates/cv-template.html` under a new name, per [reference/ats-rules.md](reference/ats-rules.md). An advert's phrase attaches only where the CV shows it, else it's a gap. State each fact once, not in profile, bullet and Skills together.
6. **Iterate.** After *every* edit, rerun `render`, `layout`, `score` — an unrendered edit is unchecked. Continue until `layout`/`repeats` pass (`--allow` for real skills) and parse ≥ 60 on every parser.
7. **Report:** before/after table, numbers only from `$CVATS score new.html --keywords kw.json --baseline original`, labelled "local ATS simulation" — never an eyeballed percentage. Then changes, gaps to confirm, assumptions.

## Rules
- Only facts the person stated or confirmed, at original strength ("helped create"; "15–20" stay) — even under pressure to "maximize the score." Unconfirmed skills/tools/achievements are gaps to confirm, never the CV.
- Never install or change anything outside this skill's venv; ask first if a real gap needs it.

## Red flags: stop and correct
| Thought | Reality |
|---|---|
| "They probably know Salesforce" / "add whatever's missing" | Unconfirmed = gap list, even under pressure |
| "The ad's phrase fits nicely here" | Only if this bullet's own evidence already shows it |
| "I'll just edit the CV file directly" | New filename; `cmp` if unsure anything changed |
| "Score 97!" / "roughly 65–70% match" | Report only `cvats score`'s number, labelled "local ATS simulation" |
| "Looks fine, I edited the HTML" | Rerun `render`, `layout`, `score` before reporting |
| Same keyword in profile, bullet and Skills | State it once, in its strongest spot |
| Trimming content for an unstated "obvious" target | Name the target assumption (role/industry/country/job-type) first |
| "I'll brew/pip install X to test this" | Use `$CVATS`; ask before touching the host |
