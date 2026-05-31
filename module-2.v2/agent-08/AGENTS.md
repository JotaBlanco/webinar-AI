# AGENTS.md — Module 2 (lateral fidelity, with skills)

You are working on the lateral-fidelity challenge. The two KPIs to minimise are in your task prompt. You have a starter toolkit of eight skills under `skills/`. They are short on purpose — short enough to read, short enough to change.

## Working directory layout

- `skills/` — toolkit. Inspect each `SKILL.md` metadata first; load the body only when relevant.
- `_shared/` — local helpers used by the skills (trajectory integration, CTE math). Plain Python; modify freely.
- `data/` — symlinked sim data (read-only).
- `code/` — symlinked baseline model code, including `ks_model.py` (read-only).
- `final-model/` — where you ship your final model. The deliverable contract is enforced by `skills/pre-flight-final-model/`.

## Skills inventory

- `score-model/` — score a `predict()` function: pooled yaw + CTE, per-segment tables, per-platform residual stats, distribution stats, **signed-bias warnings at the top of the summary** (read this before you ship — CTE is bias-dominated). Schema-aware: resolves the truth column per platform via `PLATFORM_SCHEMA`, so Tesla and any platform with a non-default column name scores instead of being silently skipped. Use as your inner-loop oracle.
- `fit-model/` — optimise per-platform coefficient dicts of an opaque model by minimising yaw RMSE, CTE RMSE, or a yaw+CTE blend, via scipy.optimize. You supply a `predict_factory(platform, coeffs)`; the skill calls it and steps the parameter vector — no knowledge of model shape required. Use when score-model's bias-check is lit up and you want a CTE-aware fit without writing scipy glue by hand.
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
