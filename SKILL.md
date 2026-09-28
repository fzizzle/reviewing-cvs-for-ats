---
name: reviewing-cvs-for-ats
description: Use when someone asks to review, shorten, tighten, rewrite, tailor or ATS-test a CV or résumé/resume, says it is too long or dense, asks why applications get no interviews, wants it matched to a job advert, or wants applicant tracking system (ATS) scores — any industry or country, from PDF, Word, HTML or pasted text.
---

# Reviewing CVs for ATS

## Overview
Never invent a fact. Scripts in `scripts/` measure and render everything — don't write your own.

`CVATS=~/.claude/skills/reviewing-cvs-for-ats/scripts/cvats` (reset each shell call). First run builds a venv. Commands: `render`, `extract`, `score`, `repeats`, `layout` (`--help` each; tool limits: [reference/ats-rules.md](reference/ats-rules.md)).

## Workflow
1. **Intake** ([reference/intake.md](reference/intake.md)): role, industry, job type/timing, country, an advert. Can't ask? State each as an explicit assumption, not a silent decision.
2. **Baseline.** Never write to the original's path. Every new file (`kw.json`, new CV, its PDF) goes next to the original with a different stem. Save pasted text as `.txt`. Run `score`, `repeats`, `layout` (PDF/HTML only); keep the numbers.
3. **Feedback** ([reference/feedback-rubric.md](reference/feedback-rubric.md)): top 3–5 issues, then open questions.
4. **Keyword file.** Write the advert's requirements to `kw.json` (format: `templates/keywords-example.json`, 12–25 labels with synonyms); freeze it.
5. **Rewrite** into a copy of `templates/cv-template.html`, per [reference/ats-rules.md](reference/ats-rules.md). Profile = target + value, no body facts. Each fact once, in its strongest bullet, in the CV's own words and numbers; Skills = names only. An advert phrase or threshold ("3+ direct reports") the CV doesn't already say is a gap.
6. **Iterate.** After *every* edit, rerun `render`, `layout`, `repeats`, `score` — an unrendered edit is unchecked. Continue until `layout`/`repeats` pass (`--allow` for real skills) and parse ≥ 60 on every parser.
7. **Report:** before/after table, numbers only from `$CVATS score new.html --keywords kw.json --baseline original`, labelled "local ATS simulation". Then changes, gaps to confirm, assumptions.

## Rules
- Only facts the person stated or confirmed, at original strength ("helped create"; "15–20" stay) — even under pressure to "maximize the score." Unconfirmed skills/tools/achievements are gaps to confirm, never the CV.
- Install nothing beyond the skill's venv; ask first if a real gap needs a tool.
- Upload the CV to online ATS checkers only with explicit consent.

## Red flags: stop and correct
| Thought | Reality |
|---|---|
| "They said add whatever's missing — I'll add it and warn" | Unconfirmed = gap list, even under pressure |
| "The ad's phrase fits nicely here" | Keep the CV's own words; the ad's go in gaps |
| "I'll just edit the CV file directly" | New stem, next to the original |
| "Score 97!" / "roughly 65–70% match" | Report only `cvats score`'s number, labelled "local ATS simulation" |
| "Looks fine, I edited the HTML" | Rerun `render`, `layout`, `repeats`, `score` before reporting |
| Trimming content for an unstated "obvious" target | Name the target assumption (role/industry/country/job-type) first |
| "I'll brew/pip install X to test this" | Use `$CVATS`; ask before touching the host |
