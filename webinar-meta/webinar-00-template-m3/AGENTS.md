# AGENTS.md — Module 3 (lateral fidelity, skills + references)

You are working on the lateral-fidelity challenge. The two KPIs to minimise are in your task prompt. You have a starter toolkit of seven skills under `skills/` and three short reference documents under `references/`. They are short on purpose — short enough to read, short enough to change.

## Working directory layout

- `skills/` — toolkit. Inspect each `SKILL.md` metadata first; load the body only when relevant.
- `references/` — short domain-knowledge documents (anti-patterns, option-space map, KPI tradeoff). Read frontmatter first; load bodies when relevant.
- `_shared/` — local helpers used by the skills (trajectory integration, CTE math). Plain Python; modify freely.
- `data/` — symlinked sim data (read-only).
- `code/` — symlinked baseline model code, including `ks_model.py` (read-only).
- `final-model/` — where you ship your final model. The deliverable contract is enforced by `skills/pre-flight-final-model/`.

## Skills inventory

- `score-model/` — score a `predict()` function: pooled yaw + CTE, per-segment tables, per-platform residual stats, distribution stats. Use as your inner-loop oracle.
- `compare-models/` — diff two `predict()` functions per-segment. Default-sorts by delta; surfaces top regressions and top improvements.
- `inspect-residuals/` — plot yaw residual against any input feature (steering, speed, time, anything else you compute) with per-platform binned mean and ±1σ band. Use when scoring-model shows a bias and you want to find which input dimension explains it.
- `visualise-segment/` — render a multi-panel PNG of one segment with truth and one or more predictions overlaid.
- `make-train-dev-split/` — produce a route-grouped train/dev split. Ships with a validator that flags route leakage.
- `load-segments/` — load segment `sim.csv`s into pandas DataFrames with consistent dtype hygiene.
- `pre-flight-final-model/` — verify that your `final-model/` bundle matches the deliverable contract.

## References inventory

Read the frontmatter (description + when-to-load) before loading the body. Recommended order on a fresh task:

- `references/anti-patterns.md` — common ways prior work has gone wrong. Load first to know what blind spots to look for.
- `references/approach-menu.md` — a map of the option space for improving on V0. Annotated by what's been explored and what hasn't.
- `references/two-kpi-tradeoff.md` — how yaw-rate RMSE and CTE RMSE relate; load after you have a working model and want to interpret your numbers.

The references are knowledge, not prescription. They describe the landscape; you choose the route.

## Working with skills and references

The skills are deliberately small. Treat them as **clay, not library**. The expected workflow when a skill's output isn't useful:

1. Look at the output. Is the signal you need *in there* somewhere?
2. If yes — extract it inline; you don't have to change the skill.
3. If no — the skill is wrong. Open the body, add the column or table you need, save, re-run.

The references work the same way — if one says something you find misleading, edit it. If a reference is in your way, delete it. The only obligation is to lower the canonical KPIs.
