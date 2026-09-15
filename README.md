# MathCraft CPA — Summative Test Sessions

A standalone Streamlit app providing 30 days of original, i-Ready-style
summative checks (Days 1-30, matching and extending your existing
`cpamathlauncher` lesson sequence), with instant autograding and a
teacher-portal results dashboard modeled on i-Ready's "Inform" view.

## What's in this folder

| Path | Purpose |
|---|---|
| `content/day01.json` ... `day30.json` | The item bank — one file per day, 5 items/day (10 on Day 30's cumulative review), each with prompt, choices/answer, rationale, and standard. |
| `content/loader.py` | Loads the item bank for the app. |
| `grading.py` | Autograding logic for multiple-choice, numeric-entry, and short-answer items. |
| `storage.py` | Pluggable data backend — local CSV (demo mode) or a private Google Sheet (recommended for real use). **Read the safety note at the top of this file before entering real student data.** |
| `roster.py` | CSV roster import, mapped from Google Classroom / PowerSchool export column names onto one canonical schema. |
| `charts.py` | Teacher-dashboard visualizations (score distributions, item difficulty, standards mastery heatmap, growth over time, and the representation/misconception research chart). |
| `app.py` | The Streamlit app itself — student test-taking flow + PIN-gated Teacher Portal. |
| `validate.py` | Structural + arithmetic validator for the item bank (re-run this after editing any day's JSON). |
| `smoke_test.py` | End-to-end test with synthetic data — exercises grading, storage, and every chart. |
| `SETUP.md` | Step-by-step deployment guide: hosting, teacher PIN, private Google Sheets storage, roster import, FERPA notes. |
| `LAUNCHER_PATCH.md` | The exact, small patch to add a "Summative Test Sessions" link to your existing `cpamathlauncher/app.py`, next to the Lessons by Day section. |

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py
```

It runs immediately in DEMO MODE (no setup required) so you can try it out.
**Before using it with real students, follow SETUP.md** — in particular the
private-storage section, since this app's eventual home repo pattern
(public GitHub + Streamlit Cloud) must never hold real student PII directly.

## Design notes worth knowing

- **Item bank is grounded in your real Day 1-10 lessons.** Days 1-4 (intro/
  data literacy) and Days 5-10 (area of rectangles → parallelograms →
  decimal/fraction bridge to percent) are built directly from the
  descriptions already in `cpamathlauncher/app.py`. Days 11-30 extend that
  arc through a standard Grade 6 sequence (Percent → Ratios & Rates →
  Expressions & Equations → Rational Numbers & the Coordinate Plane),
  inferred since no further pacing guide existed yet — **if your actual plan
  for Days 11-30 differs, tell me and I'll re-sequence the content to
  match** rather than the standards order I assumed.
- **Every numeric answer is programmatically verified** (`validate.py`
  re-evaluates each item's formula and checks it matches the stored answer)
  — all 155 items pass.
- **The height-vs-slant misconception is tracked on purpose.** `d8_q4`,
  `d9_q3`, and `d30_q2` are the same diagnostic item (same structure,
  different numbers) so the Teacher Portal's Representation Research tab can
  show whether that specific error is fading, and whether it fades
  differently by which instructional image a class saw.
- **i-Ready's actual test items are copyrighted and are not reproduced
  anywhere in this bank.** Every item here is original, written to match
  i-Ready's item types, difficulty progression, and phrasing conventions.
