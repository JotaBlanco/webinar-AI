# AGENTS.md — Module 3 (lateral fidelity, skills + references)

You are working on the lateral-fidelity challenge. The two KPIs to minimise are in your task prompt. You have a starter toolkit of eight skills under `skills/` and six short reference documents under `references/`, plus an experiment log template `EXPERIMENTS.md` at the root. They are short on purpose — short enough to read, short enough to change.

## Working directory layout

- `skills/` — toolkit. Inspect each `SKILL.md` metadata first; load the body only when relevant.
- `references/` — short domain-knowledge documents (anti-patterns, option-space map, KPI tradeoff, exploration discipline, dynamics formulations, ceiling moves). Read frontmatter first; load bodies when relevant.
- `EXPERIMENTS.md` — append-only log of approaches you've tried. Maintain it as you go.
- `_shared/` — local helpers used by the skills (trajectory integration, CTE math). Plain Python; modify freely.
- `data/` — symlinked sim data (read-only).
- `code/` — symlinked baseline model code, including `ks_model.py` (read-only).
- `final-model/` — where you ship your final model. The deliverable contract is enforced by `skills/pre-flight-final-model/`.

## Skills inventory

- `score-model/` — schema-aware scorer for any `predict()` function across all platforms: pooled yaw + CTE, per-segment tables, per-platform signed-bias warnings, distribution stats. Use as your inner-loop oracle.
- `fit-model/` — model-agnostic per-platform coefficient fitter against yaw / CTE / yaw+CTE objectives. You supply a `predict_factory(platform, coeffs)`; the skill runs scipy and returns fitted coeffs. Use when bias-warnings light up or you want a CTE-aware fit.
- `compare-models/` — diff two `predict()` functions per-segment. Default-sorts by delta; surfaces top regressions and top improvements.
- `inspect-residuals/` — plot yaw residual against any input feature (steering, speed, time, anything else you compute) with per-platform binned mean and ±1σ band. Use when scoring-model shows a bias and you want to find which input dimension explains it.
- `visualise-segment/` — render a multi-panel PNG of one segment with truth and one or more predictions overlaid.
- `make-train-dev-split/` — produce a route-grouped train/dev split. Ships with a validator that flags route leakage.
- `load-segments/` — load segment `sim.csv`s into pandas DataFrames with consistent dtype hygiene.
- `pre-flight-final-model/` — verify that your `final-model/` bundle matches the deliverable contract.

## References inventory

Read the frontmatter (description + when-to-load) before loading the body. Recommended order on a fresh task:

- `references/exploration-discipline.md` — protocol for naming alternatives before committing and logging what you try. Load at the start.
- `references/anti-patterns.md` — common ways prior work has gone wrong, plus the legal per-segment-bias recipe with worked example. Load first to know what blind spots to look for.
- `references/approach-menu.md` — a map of the option space for improving on V0. Annotated by what's been explored, what's lightly tried, and what's unexplored. Includes a platform-gating diagnostic and a structural-complexity ladder.
- `references/dynamics-formulations.md` — V0 documented in full plus sketches of higher-rung formulations (linear dynamic ST with slip angles, nonlinear tyre, multi-body). **Living doc — append your formulation here when you ship one past V0.**
- `references/two-kpi-tradeoff.md` — how yaw-rate RMSE and CTE RMSE relate. Load after you have a working model and want to interpret your numbers; the worked example shows the per-platform bias-spread diagnostic.
- `references/ceiling-moves.md` — four unexplored moves above the current best-known ceiling. Load only after you've already beaten V0 by ≥+30% on both KPIs — loading earlier wastes the doc.

The references are knowledge, not prescription. They describe the landscape; you choose the route. Each ends with a "failure-mode index" — a checklist of "you'll see this if…" patterns to verify before committing.

## Working with skills and references

The skills are deliberately small. Treat them as **clay, not library**. The expected workflow when a skill's output isn't useful:

1. Look at the output. Is the signal you need *in there* somewhere?
2. If yes — extract it inline; you don't have to change the skill.
3. If no — the skill is wrong. Open the body, add the column or table you need, save, re-run.

The references work the same way — if one says something you find misleading, edit it. If a reference is in your way, delete it. The only obligation is to lower the canonical KPIs.

## On exploration

Before committing to your first approach, read `references/exploration-discipline.md` and **name at least five genuinely different approaches** you might try — and at least **three of those five must be different model structures**, not five flavours of the same model. (See `references/approach-menu.md` § "Physics-based options — a ladder" for what "different structure" means here.) Pick one. Try it. Score it. Append an entry to `EXPERIMENTS.md`. Only then consider the next.

The single biggest failure pattern in past cohorts isn't running out of time — it's silent re-convergence on the same idea wearing a different variable name. The log is what catches that. The structure-diversity rule is what forces you to consider climbing a rung instead of refining coefficients on your current one.
