---
name: reviewing-cvs-for-ats
description: Use when someone asks to review, shorten, tighten, rewrite, tailor or ATS-test a CV or résumé/resume, says it is too long or dense, asks why applications get no interviews, wants it matched to a job advert, or wants applicant tracking system (ATS) scores — any industry or country, from PDF, Word, HTML or pasted text.
---

# Reviewing CVs for ATS

## Overview
Never invent a fact. Scripts in `scripts/` measure and render — don't write your own.

`CVATS=~/.claude/skills/reviewing-cvs-for-ats/scripts/cvats`. Commands: `render`, `extract`, `score`, `repeats`, `layout`, `fidelity` (`--help` each).

## Workflow
1. **Intake** ([reference/intake.md](reference/intake.md)): role, industry, job type/timing, country, an advert. Can't ask? State each as an assumption, not a silent decision.
2. **Baseline.** Never write to the original's path. New files (`kw.json`, new CV, PDF) go beside it under a different stem, case-insensitively (`foo.pdf`/`Foo.PDF` collide). Save pasted text as `.txt`. Run `score`, `repeats`, `layout` (PDF/HTML).
3. **Feedback** ([reference/feedback-rubric.md](reference/feedback-rubric.md)): top 3–5 issues.
4. **Keyword file.** Write requirements to `kw.json` ([reference/ats-rules.md](reference/ats-rules.md)); freeze it.
5. **Rewrite** into a copy of `templates/cv-template.html`, per ats-rules.md. Profile = target + value, no body facts. Each fact once, in its strongest bullet, in the CV's own words and numbers. Any advert word, phrase, threshold or relabelling the CV doesn't already say ("demand generation", "3+ direct reports") is a gap, not a tagline or skill.
6. **Iterate.** After *every* edit rerun `render`, `layout`, `repeats`, `score`, `fidelity` — an unrendered edit is unchecked. Pass = exit code 0, not a summary: loop until `layout`, `repeats` (`--allow` real skills) and `fidelity` exit 0, and parse ≥ 60 where facts allow.
7. **Report**, in this order:
   - Before/after table from `$CVATS score new.html --keywords kw.json --baseline original`, labelled "local ATS simulation".
   - Final `layout`/`repeats`/`fidelity` lines and exit codes, verbatim.
   - Gaps: every score `problems` line and sub-score below max — fixed or listed, none dropped.
   - Changes, then assumptions.

## Rules
- Only facts the person stated or confirmed, at original strength ("helped create"; "15–20" stay) — even under score pressure. Anything unconfirmed (skill, tool, achievement, location, link, month-date) is a gap, never the CV.
- `fidelity --confirmed` takes only items the person confirmed — quote them; the rest comes out.
- Upload to online ATS checkers only with consent.

## Red flags: stop and correct
| Thought | Reality |
|---|---|
| "They said add it — I'll warn after" | Unconfirmed = gap list, even under pressure |
| "The ad's phrase fits nicely here" | Own words only; the ad's phrases go in gaps |
| "I'll just edit the CV file directly" | New stem, next to the original |
| "I'll brew/pip install X" | Install nothing beyond the skill's venv; ask first |
| "'Helped with X' reads better as 'Carried out X'" | Supporting verbs (helped, assisted, supported, contributed) stay supporting |
| "I'll infer their city and flag it as an assumption" | Flagged or not, an unconfirmed location is a gap |
