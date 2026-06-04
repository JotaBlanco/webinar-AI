# AGENTS.md — Module 2.v3 (lateral fidelity, with skills)

You are working on the lateral-fidelity challenge. The two KPIs to minimise are in your task prompt. You have a starter toolkit of ten skills under `skills/`. They are short on purpose — short enough to read, short enough to change.

## Working directory layout

- `skills/` — toolkit. Inspect each `SKILL.md` metadata first; load the body only when relevant.
- `_shared/` — local helpers used by the skills (trajectory integration, CTE math). Plain Python; modify freely.
- `data/` — symlinked sim data (read-only).
- `code/` — symlinked baseline model code, including `ks_model.py` (read-only).
- `final-model/` — where you ship your final model. The deliverable contract is enforced by `skills/pre-flight-final-model/`.

## Skills inventory

- `score-model/` — score a `predict()` function: pooled yaw + CTE, per-segment tables, per-platform residual stats, distribution stats, **signed-bias warnings at the top of the summary** (read this before you ship — CTE is bias-dominated). Schema-aware: resolves the truth column per platform via `PLATFORM_SCHEMA`, so Tesla and any platform with a non-default column name scores instead of being silently skipped. Use as your inner-loop oracle.
- `fit-model/` — optimise per-platform coefficient dicts of an opaque model by minimising yaw RMSE, CTE RMSE, or a yaw+CTE blend, via scipy.optimize. You supply a `predict_factory(platform, coeffs)`; the skill calls it and steps the parameter vector — no knowledge of model shape required. The summary opens with **🚨 fit warnings** (co-collapse / overfit / stuck-on-bound / non-convergence) and the per-platform table shows the **train/dev gap inline**. Pass `bounds` whenever you have physical intuition — it switches the optimiser to L-BFGS-B and stops co-degenerate solutions from being picked.
- `residual-structure/` — after a fit, characterise what's LEFT in the residual: autocorrelation at multiple lags (memory → dynamic term), correlation with each input feature AND its time-derivative (rate-dependent → derivative term), and sign-asymmetry in δ (cubic / hysteresis). Returns a per-platform **verdict** — `noise_floor` (you're done) or `structure_detected` with a specific reason ("residual autocorrelated at lag 6 → try a τ·d(δ)/dt term"). The v2 cohort hit a yaw ceiling because almost everyone shipped V1 understeer; the one winner saw exactly this autocorrelation signature and added a steering-rate lead. This is the bridge between "I fit V1" and "should I build V2?".
- `route-bias/` — once you've fitted, group residuals by `(platform, route)` and rank routes by their share of the *platform's* pooled error, not just by their own RMSE. Includes per-route means of input features so you can correlate route bias against an OBSERVABLE feature (route ID is not an inference input, so you cannot apply a route-keyed correction directly — you use this to discover an input feature to add to your model).
- `compare-models/` — diff two `predict()` functions per-segment. Default-sorts by delta; surfaces top regressions and top improvements.
- `inspect-residuals/` — plot yaw residual against one input feature (1-D scatter + binned mean ± σ band) OR two features (2-D heatmap of mean residual per cell, with a diverging colour scale so signed bias jumps out). Use 2-D when the residual depends on speed AND steering simultaneously (understeer is `v² × delta`; a 1-D plot folds one axis into noise). Schema-aware.
- `visualise-segment/` — render a multi-panel PNG of one segment with truth and one or more predictions overlaid.
- `make-train-dev-split/` — produce a route-grouped train/dev split. Ships with a validator that flags route leakage.
- `load-segments/` — load segment `sim.csv`s into pandas DataFrames with consistent dtype hygiene.
- `pre-flight-final-model/` — verify that your `final-model/` bundle matches the deliverable contract.

## Suggested loop

The skills are designed to chain, not to fork. A typical iteration:

1. **Score** the current `predict_fn` with `score-model`. Read the **signed-bias check** at the top of the summary first. If a platform is flagged, the bias is what's killing CTE — fixing it is higher leverage than tuning yaw RMSE.
2. **Fit** with `fit-model`. Pass `bounds` if you have physical intuition. Pass `dev_segments` so the table shows the train/dev gap inline — that's how you catch overfit before shipping. Look at the **fit warnings** block on top: co-collapse means your parameterisation is degenerate; wide gap means your model is too flexible for your split.
3. **Diagnose what's left.** After the fit, run `residual-structure` — does the verdict say `noise_floor` or `structure_detected`? If `noise_floor`, stop. If `structure_detected`, the reason names a specific term to add. Re-score. If a platform's CTE is still drifting, run `route-bias` to see which routes dominate the residual. Use `inspect-residuals` (1-D or 2-D) to confirm the input feature that correlates with the bias.
4. **Iterate the model**, not the fit. Add a term that depends on the feature you found, rebuild `predict_factory`, refit, re-score.

## Don't ship V1

The v2-cohort yaw-RMSE ceiling came from one specific failure mode: agents fitted V1 understeer (`v·δ / (L + K_us·v²)`), saw the per-platform bias collapse, and shipped. The single agent who beat the cohort by 9% saw that the V1 residual was *autocorrelated* (because steering measurement and yaw measurement have different pipeline delays) and added a `τ·d(δ)/dt` lead term to make V2. V1 was good. V2 was better. Without V2, V1 looks like the ceiling.

So: **after your first fit, run `residual-structure` and build a second candidate model** that differs structurally from your first — a derivative term, a regime-conditional split, a cubic, whatever the verdict points at. Fit it. Diff it against V1 with `compare-models`. *Then* decide what to ship.

This is the most important loop discipline in this template. Agents who stop at V1 ship V1.

## Working with skills

The skills are deliberately small. Treat them as **clay, not library**. The expected workflow when a skill's output isn't useful:

1. Look at the output. Is the signal you need *in there* somewhere?
2. If yes — extract it inline; you don't have to change the skill.
3. If no — the skill is wrong. Open the body, add the column or table you need, save, re-run.

If a skill is in your way, delete it. The only obligation is to lower the canonical KPIs.
