# AGENTS.md — Module 2 (lateral fidelity, with skills)

You are working on the lateral-fidelity challenge. The two KPIs to minimise are in your task prompt. You have a starter toolkit of six skills under `skills/`. They are short on purpose — short enough to read, short enough to change.

## Working directory layout

- `skills/` — toolkit. Inspect each `SKILL.md` metadata first; load the body only when relevant.
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

## Working with skills

The skills are deliberately small. Treat them as **clay, not library**. The expected workflow when a skill's output isn't useful:

1. Look at the output. Is the signal you need *in there* somewhere?
2. If yes — extract it inline; you don't have to change the skill.
3. If no — the skill is wrong. Open the body, add the column or table you need, save, re-run.

If a skill is in your way, delete it. The only obligation is to lower the canonical KPIs.
