# AGENTS.md — Module 2 (lateral fidelity, with skills)

You are working on the lateral-fidelity challenge. You have a starter toolkit of six skills under `skills/`. Use them, modify them, or replace them as your work demands. The skills are starting points, not law.

## Working directory layout

- `skills/` — toolkit. Inspect each `SKILL.md` to decide whether to load its body.
- `_shared/` — internal helpers used by the skills (trajectory integration, CTE math). Treat as library code.
- `data/` — symlinked sim data (read-only).
- `code/` — symlinked baseline model code, including `ks_model.py` (read-only).
- `final-model/` — where you ship your final model. Required by the deliverable contract in your task brief.

## Skills inventory

Inspect SKILL.md metadata first — never load all bodies eagerly.

- `score-model/` — score any `predict()` function against your data. Returns yaw-rate RMSE, CTE RMSE, plus per-platform and per-regime breakdowns.
- `compare-models/` — diff two `predict()` functions per-segment to see where one beats the other.
- `visualise-segment/` — render a multi-panel PNG of one segment with truth and one or more predictions overlaid.
- `make-train-dev-split/` — split your data into train and dev sets for honest iteration while you build.
- `load-segments/` — load segment `sim.csv`s into pandas DataFrames with consistent dtype hygiene.
- `pre-flight-final-model/` — sanity-check that your `final-model/` bundle is shaped the way the deliverable contract requires.

## Your real measure of progress

The two primary KPIs defined in your task brief. The skills compute them; nothing else is the score.

## Permission

You may modify, extend, or delete any skill. If a skill is wrong or in your way, fix it or ship without it. The only obligation is to lower the canonical KPIs.
