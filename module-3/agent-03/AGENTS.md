# AGENTS.md — Module 3 (lateral fidelity, skills + references)

You are working on the lateral-fidelity challenge. The two KPIs to minimise are in your task prompt. You have a starter toolkit of skills under `skills/` and short reference documents under `references/`, plus an experiment log template `EXPERIMENTS.md` at the root. They are short on purpose — short enough to read, short enough to change.

## Operating contract — what your `predict()` will see at grading time

The canonical grader hands your `predict(sim_df, platform)` a DataFrame containing **only these eight input columns**:

| column | meaning |
|---|---|
| `t_s` | sample time (s) |
| `delta_wheel_deg` | hand-wheel angle (deg) |
| `delta_road_rad` | road-wheel angle (rad) — the steering channel to use in physics models |
| `v_mps` | vehicle speed (m/s) |
| `a_long_mps2` | longitudinal acceleration (m/s²) |
| `accel_pedal_pct` | accelerator pedal position (%) |
| `brake_pressed` | brake-pressed flag (0/1) |
| `yaw_rate_pred_rads` | V0 baseline yaw rate (rad/s) — the column your `predict()` is replacing |

**Anything else will raise `KeyError`.** Three notable absences to be aware of:

- **`yaw_rate_meas_rads`** — the truth channel. Denied because it's what the grader scores against.
- **`a_lat_meas_mps2`** — lateral acceleration. Denied because in this dataset it's computed kinematically from truth yaw rate (`a_lat = v · ψ̇_truth`), so using it is equivalent to peeking at truth up to a `v` factor. **Some recipes and intuitions point to `a_lat_meas` as a useful straight-row detector. Don't import them verbatim — always substitute an allowlist proxy** (e.g. `v_mps * yaw_rate_pred_rads`, or `|yaw_rate_pred_rads|`, or `|delta_road_rad|`).
- **`yaw_rate_resid_rads`, `a_y_resid_mps2`, `x_m`, `y_m`, `psi_rad`** — denied (direct or integrated truth leaks).

The local `data/` tree contains TWO views of the same segments:
- **`data/sim-only/segments/`** — agent-facing view. Only the 8 allowlist columns. The local `score-model` skill and `pre-flighting-final-model` use this — so your local numbers match the canonical grader's numbers.
- **`data/sim/segments/`** — full-fidelity view including truth. Useful for *offline* fitting (e.g. with `fit-model`), but anything your `predict()` reads from this set will silently break at grading time. If you write `sim_df["a_lat_meas_mps2"]` and test against `data/sim/`, it works locally and fails the moment preflight or the grader strips the input to the allowlist.

The Tesla platform has no `yaw_rate_meas_rads` channel (no truth) — V0 passthrough is the honest fallback. Don't fit Tesla.

## The highest-leverage move on this dataset

If past cohort grades are any guide, **the single biggest yes/no decision on this dataset is whether you ship per-segment δ₀ estimation, platform-gated**. In the most recent graded m3 cohort, the three top-tier agents (yaw +56-57%, CTE +67-72% over V0) all shipped it; the three bottom-tier agents (yaw +48-50%, CTE +55%) all didn't, despite identical model form otherwise. That single recipe is worth ~8 pts of yaw and ~15 pts of CTE.

**Read `references/anti-patterns.md` § "The legal cousin" early.** It contains the recipe, the platform-gating rule (Mach-E and Hyundai IONIQ-5: on; Lightning: off), and a worked example using only allowlist channels. This is not a "watch out for" warning — it's a positive recipe disguised as one because the doc also documents the *illegal* truth-peeking version next to it.

This is not the only ceiling. The rung-0 local optimum (KS + understeer + lag + per-segment δ₀) tops out around +55-60% yaw / +65-70% CTE. To get past that, see `references/dynamics-formulations.md` for structural climbs (rung 1 dynamic single-track with slip angles, rung 2 nonlinear tyre).

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
- `fit-model/` — model-agnostic per-platform coefficient fitter against yaw / CTE / yaw+CTE objectives. You supply a `predict_factory(platform, coeffs)`; the skill runs scipy and returns fitted coeffs **plus post-fit diagnostics** — co-collapse, stuck-on-bound, overfit-gap, non-convergence. Train/dev gap surfaces inline when `dev_segments` is passed. Pass `bounds` whenever you can.
- `compare-models/` — diff two `predict()` functions per-segment. Default-sorts by delta; surfaces top regressions and top improvements.
- `inspect-residuals/` — plot yaw residual against one OR two input features. 1-D scatter + binned mean/σ; 2-D heatmap of mean residual over (x, y) cells. Schema-aware (Tesla, IONIQ, any platform).
- `residual-structure/` — diagnose what's *left* in the residual after a fit: temporal autocorrelation at multiple lags, correlation with each input feature AND its time-derivative, sign-asymmetry. Returns a per-platform **verdict** (`"noise_floor"` → stop; `"structure_detected"` → specific reason like "autocorrelated at lag 6 → try a steering-rate term"). The bridge between "I fit it" and "is V2 worth building?". A key signal for whether to climb a rung.
- `route-bias/` — per-route signed yaw bias and CTE drift ranked by each route's share of platform pooled error, with per-route input-feature means. Use after a fit when scoring-model still flags bias but per-platform fit has plateaued. Route ID isn't an inference input — output is diagnostic, used to discover an observable input feature you should add.
- `visualise-segment/` — render a multi-panel PNG of one segment with truth and one or more predictions overlaid.
- `make-train-dev-split/` — produce a route-grouped train/dev split. Ships with a validator that flags route leakage.
- `load-segments/` — load segment `sim.csv`s into pandas DataFrames with consistent dtype hygiene.
- `pre-flight-final-model/` — verify that your `final-model/` bundle matches the deliverable contract. Tests every platform declared in `manifest.platform_support`, not just one — catches platform-conditional failures.

## References inventory

Read the frontmatter (description + when-to-load) before loading the body. Recommended order on a fresh task:

- `references/exploration-discipline.md` — protocol for naming alternatives before committing and logging what you try. Load at the start.
- `references/anti-patterns.md` — common ways prior work has gone wrong, plus the **per-segment δ₀ recipe** (§ "The legal cousin") which is the highest-leverage move on this dataset. Load first.
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

## On exploration — the default is to climb

Past cohorts have a near-universal failure mode: every agent ships a refined rung-0 model (kinematic single-track + understeer + lag, with better coefficients). Nobody attempts rung 1 (linear dynamic single-track with slip angles) or above. The reports show this isn't lack of awareness — agents *consider* climbing and reject it, because rung-0 refinements are reliable and rung 1 looks expensive. The result is the cohort piles up at the same local optimum and we don't learn whether rung 1 actually helps on this data.

**The default in this template is now: ship a structural climb attempt.** Refining rung 0 stays available, but it's no longer the default path. Concretely:

1. **Your `EXPERIMENTS.md` must contain at least one entry tagged `Rung: 1` (or higher, or `orthogonal`).** This is enforced by `pre-flighting-final-model` — a bundle without a logged climb attempt does not pass. The attempt does **not** have to be your shipped model; it has to be a real, scored attempt that you ran and logged.
2. **If your shipped model is rung 0**, the log entry for the climb attempt must include a comparison against your rung-0 model on dev and a one-line reason for falling back.
3. **The "Minimum viable rung-1 attempt" recipe** in `references/dynamics-formulations.md` § "Rung 1" gives you a ~30-line scaffolded climb. Use it as a starting point; the cost-to-attempt is lower than past cohorts assumed.

The point isn't to force-ship climbed models — your safety net is the rung-0 fallback. The point is to **generate evidence**, in this cohort, about whether rung 1 helps on this dataset. We don't have that evidence yet because nobody has tried.

Read `references/exploration-discipline.md` for the full protocol (5 named alternatives, the experiment log schema). The `Rung:` field is now required on every `EXPERIMENTS.md` entry.

## A workable inner-loop on this task

This is a recipe, not a rule. Adapt freely.

1. **Score V0 with `score-model`** to establish the floor and see the per-platform residual breakdown.
2. **Run the per-platform bias-spread diagnostic** (see `references/two-kpi-tradeoff.md` § "Worked example") *before* you start fitting. For each platform, compute `std(per_segment_yaw_residual_mean)`:
   - `std > 0.002 rad/s` → that platform will benefit from per-segment δ₀.
   - `std < 0.002 rad/s` → that platform won't; use a global δ₀ there.
   This gate determines `use_per_segment_delta0=True/False` per platform in your first model. Skipping the gate is how top-tier and bottom-tier outcomes diverge.
3. **Write a reconstruction-shape `predict()`** (see `references/approach-menu.md` § "Two model *shapes*") with per-platform `{g, L_eff, K_us, tau, delta0, use_per_segment_delta0}`. Use `fit-model` to fit coefficients per platform on `data/sim/` against the yaw or yaw+CTE objective.
4. **Score with `score-model`** and check residual shape per regime (straight/steady/transient). If transient dominates, see the "climb the ladder" path in `references/approach-menu.md`. If straight/steady dominates, refine coefficients or polynomial steering scale.
5. **Log each attempt to `EXPERIMENTS.md`** with the hypothesis, the change, the result, and the required `Rung:` tag (`0` / `1` / `2` / `3` / `orthogonal`).
6. **Before shipping any rung-0 model, run a rung-1 attempt** following the "Minimum viable rung-1 attempt" recipe in `references/dynamics-formulations.md` § "Rung 1". Even if it doesn't beat your rung-0 model, log it. This is enforced — see § "On exploration" above.
7. **Before declaring done**, run the deliverable-hygiene checklist below.

The other failure pattern past cohorts produce is silent re-convergence on the same approach wearing a different variable name. The `EXPERIMENTS.md` log + the required `Rung:` tag is what catches both: it makes structurally-different attempts visible *to yourself*, and it makes "I tried 8 flavours of the same coefficient tweak" mechanically detectable when every entry is `Rung: 0`.

## Before declaring done — deliverable hygiene checklist

This is the final gate before you stop. Skipping it is the single most common way agents lose graded points to packaging mistakes rather than to weak models.

1. **Run `pre-flighting-final-model`** on your `final-model/` bundle and confirm every check passes. It catches:
   - missing `predict.py`, `manifest.json`, `REPORT.md` (≥100 bytes)
   - missing sibling files referenced by `predict.py` (e.g. `coeffs.json` that you forgot to ship — caught at the `predict_imports` step)
   - reads from denied columns like `a_lat_meas_mps2` (the dry-run uses `data/sim-only/` so allowlist violations surface)
   - per-platform `KeyError`/exception paths in your predict (the dry-run iterates every platform declared in `manifest.platform_support`)
2. **Read your manifest's `platform_support`** out loud. Does every entry have a corresponding code path in `predict()`? If you declared support for IONIQ-5 but `coeffs.json` only has Mach-E and Lightning, your IONIQ-5 segments will silently fall through to V0 passthrough at grading time — you ship +0% on a third of the pool.
3. **List your `final-model/` directory contents.** Every file your `predict.py` opens at import time or at call time must be present.
4. **Confirm your `EXPERIMENTS.md` contains at least one `Rung: 1+` or `Rung: orthogonal` entry.** Preflight checks this — see § "On exploration" for why.

If any check fails, fix and re-run. Don't ship a bundle that doesn't pass preflight.
