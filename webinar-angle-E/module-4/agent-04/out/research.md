# Phase 1 — Research notes

## Platforms & truth
- `FORD_MUSTANG_MACH_E_MK1`: 315 sim.csv, ~914k rows. Has `yaw_rate_meas_rads` truth.
- `FORD_F_150_LIGHTNING_MK1`: 230 sim.csv, ~667k rows. Has truth.
- `TESLA_MODEL_3`: present but no lateral truth channel — out of scope.
- dt is uniform ~20 ms (50 Hz) on the sampled segment.

## Baseline `yaw_rate_resid_rads` (no preprocessing)
| platform | n | RMSE (rad/s) | straight RMSE / bias | steady RMSE / bias | transient RMSE / bias |
|---|---|---|---|---|---|
| Mach-E | 913,626 | 0.01613 | 0.00859 / -0.00068 | 0.04156 / +0.00316 | 0.05543 / +0.00788 |
| Lightning | 667,141 | 0.02037 | 0.00976 / -0.00411 | 0.05217 / +0.00035 | 0.05314 / -0.00375 |

Regime tags (crude pass): `|yr_meas|<0.05` straight, `|dyr|<0.005` steady, else transient.

## Anomalies / observations
- No NaN residuals on either platform (good — clean).
- Mach-E shows a consistent **positive bias in transient** (+0.0079) — KS under-yaws in fast-steer regime.
- Lightning has a **larger negative bias in straight** (-0.0041) — sign drift on near-zero steer (likely steering offset).
- Transient n is small (~1% of rows). Sample-driven RMSE for that bucket is fragile.
- Steady-state RMSE >> straight RMSE on both — classic KS understeer-gradient miscalibration.

## Open questions before picking a ladder
- Is the regime split worth weighting (transient is rare but dominates error visually)?
- Does a simple steering-offset removal kill most of the straight-line bias on Lightning?
- Is V3 (linear ST fit) overfitting risk acceptable with ~900k rows on Mach-E? (Probably yes.)
- Which platform — Mach-E has more data and cleaner straight-line bias, so it's the better testbed.
- Should attribution be marginal-vs-prior or marginal-vs-V0? Skill says marginal-vs-prior; lock that.
