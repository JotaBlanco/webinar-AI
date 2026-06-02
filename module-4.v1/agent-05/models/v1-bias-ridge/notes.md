# v1-bias-ridge

Parent: v1_baseline (m3.v2 ceiling).
Rung: orthogonal residual learner (cohort-evidenced §2 + §4).

## What this differs from

Differs from V1 in two stacked corrections applied on top of the V1 yaw-rate prediction, both per-platform:

1. **Signed bias correction.** A single additive constant per platform, fitted as the pooled mean residual `(yaw_truth - yaw_v1)` across all training samples with `v_mps > 2`. Cohort §2 documents the persistent biases that the bias correction removes (Mach-E and IONIQ-5 carry signed yaw biases that V1 cannot recover because its lever set has no DC offset term; Lightning's bias is near noise floor).

2. **Ridge residual-learner head.** A 14-feature linear model trained per-platform with ridge regularisation, fitted on `(yaw_truth - yaw_v1 - bias)`. Features are all derived from the 8-column allowlist (no truth leak): `yr_v1`, `|yr_v1|`, `v*yr_v1` (a_lat proxy), `delta`, `|delta|`, `dδ/dt`, `|dδ/dt|`, `v`, `v*delta`, `v*yr_v1`, `a_long`, `brake`, `accel`, `d(yr_v1)/dt`. Lambda chosen per-platform from {1, 10, 30, 100, 300, 1000, 3000, 10000} by held-out resid-RMSE on a segment-hashed 80/20 split. The head is only applied when its dev resid RMSE is strictly better than bias-only — IONIQ-5's ridge converged on `lambda=10000` with no improvement, so on IONIQ-5 we ship bias-only.

Tesla falls through to V0 passthrough (no truth channel).

## Why not other things

- Rung-1 dynamic ST: cohort §1 + §7 — every cohort attempt failed under budget. Skipped.
- Steering-rate FF (`k_dd`, lead-compensator): cohort §3 — zero-within-noise. Skipped.
- Lag-τ refitting: cohort §8 — lag is mis-modelling a non-linear structure, not transient. Skipped.
- Asymmetric (left/right) bias gate: cohort §6 — overfits on subsets. Skipped.

## Expected residual character

Residual on this model should be near-symmetric (bias removed), uncorrelated with `δ, v, dδ/dt` after the ridge head subtracts the linear projection. Remaining error is the high-rank non-linear (δ, dδ/dt, v) interaction structure that cohort §8 identifies — a true state-space rung-1 model would attack that, but is out of budget.
