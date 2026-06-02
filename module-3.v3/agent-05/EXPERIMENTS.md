# EXPERIMENTS.md

Append-only log of attempts. One entry per concrete attempt.

## Alternatives considered

- (structure) **v1-debiased** — V1 + per-platform additive yaw bias `b_p`. Attacks the per-platform signed CTE drift (Mach-E -22 m, IONIQ-5 -12 m). Smallest structural change that touches the dominant residual.
- (structure) **v1-debiased-kdd** — V1 + bias + `k_dd · d(δ_road)/dt`. Attacks transient-regime yaw error (V1 yaw RMSE 0.0165 transient vs 0.0044 straight) with a feature-engineered residual learner.
- (structure) **dynamic-single-track (rung-1)** — proper lateral-dynamics ODE with front/rear slip angles and linear tyre coefficients. Replaces V1's kinematic single-track + lag entirely. Attacks transient regime at its source. NOT BUILT — out of time budget.
- (structure) **complementary-filter** — low-pass V1 yaw + high-pass steering-derivative blend at a tuned cutoff. Attacks the trade-off between V1's straight-line accuracy and its transient lag. NOT BUILT.
- (structure) **per-route bias residual** — fit a per-route yaw bias from input features (no truth) using e.g. mean(delta_road) over the segment as a regressor. Attacks the residual CTE drift that the per-segment δ₀ couldn't catch. NOT BUILT.
- (refines-v1) **V1 with tighter understeer/τ refit** — sanity-check that the m3.v2 ceiling really is converged. Skipped: cohort already proved it spreads 0.3 pp.
- (orthogonal) **ensemble V1 yaw with V0 passthrough in straight regime** — non-modelling intervention. Skipped: V0 is strictly worse than V1 on straights too.

## E00 — V1 baseline
- Hypothesis: pre-shipped ceiling. Score to confirm the floor.
- Result (dev pooled): yaw 0.005874; CTE 56.81.
- Per-platform: Lightning 0.00566 / 62.18; Mach-E 0.00859 / 98.68; IONIQ-5 0.00766 / 69.53.
- Verdict: baseline.

## E01 — v1-debiased
- Model dir: models/v1-debiased/
- Hypothesis: V1's per-platform signed-CTE drift (-22 m on Mach-E, -12 m on IONIQ-5) is a yaw-bias signature. A constant additive correction per platform should land the bulk.
- What I changed: per-platform scalar offset added to V1's yaw_rate_pred_rads.
- Fit: grid scan around the mean-residual analytical optimum, minimised normalised (yaw_rmse + cte_rmse) per platform.
- Result (dev pooled): yaw 0.005874 → **0.005844** (-0.5%); CTE 56.81 → **54.19** (-4.6%).
- Per-platform CTE: Mach-E 98.68 → 91.26 (-7.5%); IONIQ-5 69.53 → 67.03 (-3.6%); Lightning 62.18 → 62.18 (no change, V1 already at noise floor).
- Per-platform signed CTE drift: Mach-E -22 → -5; IONIQ-5 -12 → +1; Lightning +0.3 → -1.
- Verdict: **keep — ship this**.
- Things this rules out: most of Mach-E's CTE excess vs Lightning is *bias*, not noise. A bias-correcting term is the right shape; the remaining gap is dynamic.

## E02 — v1-debiased-kdd
- Model dir: models/v1-debiased-kdd/
- Hypothesis: V1's transient-regime yaw error (0.0165 rad/s vs 0.0044 straight) is partly correctable with a linear-in-steering-rate residual term. d(δ_road)/dt is the obvious input-only proxy.
- What I changed: added `+ k_dd · d(δ_road)/dt` on top of v1-debiased; grid-scanned k_dd ∈ [-0.2 .. +0.2] per platform.
- Result (dev pooled): yaw 0.005844 → 0.005842; CTE 54.19 → 54.19. Essentially no movement.
- Best k_dd per platform: Lightning -0.010, Mach-E -0.010, IONIQ-5 0.000.
- Verdict: **shelve**. The signal a linear term in d(δ)/dt can extract has already been absorbed by V1's first-order lag.
- Things this rules out: a *linear* residual term in steering rate is not what's left. To attack transient further you need a model with actual lateral-dynamics state — a rung-1 dynamic bicycle ODE — not a residual gain.
