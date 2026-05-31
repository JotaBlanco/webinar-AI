# AGENTS.md — Module 3 (lateral fidelity, skills + references)

You are working on the lateral-fidelity challenge. You have a starter toolkit of six skills under `skills/` and three reference documents under `references/`. Use them, modify them, or replace them as your work demands. They are starting points, not law.

## Working directory layout

- `skills/` — toolkit. Inspect each `SKILL.md` to decide whether to load its body.
- `references/` — short domain-knowledge documents about anti-patterns, the option space, and how to read the two KPIs. Read metadata first; load bodies when relevant.
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

## References inventory

Read the frontmatter (description + when-to-load) before loading the body. Recommended order on a fresh task:

- `references/anti-patterns.md` — common ways prior work has gone wrong. Load first to know what blind spots to look for.
- `references/approach-menu.md` — a map of the option space for improving on V0. Annotated by what's been explored and what hasn't.
- `references/two-kpi-tradeoff.md` — how yaw-rate RMSE and CTE RMSE relate; load after you have a working model and want to interpret your numbers.

The references are knowledge, not prescription. They describe the landscape; you choose the route.

## Your real measure of progress

The two primary KPIs defined in your task brief. The skills compute them; nothing else is the score.

## Permission

You may modify, extend, or delete any skill or reference. If something is wrong or in your way, fix it or ship without it. The only obligation is to lower the canonical KPIs.
