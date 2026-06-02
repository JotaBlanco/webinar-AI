# MODELS.md — registry of candidate models

V1 floor (sim/segments, allowlist-stripped — local==canonical): `yaw_rmse = 0.005874 rad/s`, `cte_rmse = 56.81 m`.

---

## v1_plus_delta0
- dir: models/v1_plus_delta0/
- structure: refines-v1
- status: shelved
- pooled-yaw-rmse-dev: 0.006012
- pooled-cte-rmse-dev: 69.70
- verdict: Lost. Enabling per-segment δ₀ on Lightning breaks the fit (Lightning's calibration is stable at a fixed δ₀; per-seg median introduces noise). Shelved.

## v1_plus_ddelta
- dir: models/v1_plus_ddelta/
- structure: differs-from-v1
- status: shelved
- pooled-yaw-rmse-dev: 0.005872
- pooled-cte-rmse-dev: 56.81
- verdict: Marginal yaw gain only. Attacks transient residual via additive feed-forward k_ff·d(δ)/dt term; structurally distinct (V1 has no derivative input), but the gain is absorbed once the affine bias correction is applied. Shelved as redundant.

## v1_affine
- dir: models/v1_affine/
- structure: refines-v1
- status: shipped
- pooled-yaw-rmse-dev: 0.005815
- pooled-cte-rmse-dev: 54.48
- verdict: Shipped. Post-hoc affine (s, b) per platform zeros out the signed yaw bias on Mach-E and IONIQ-5 that drives V1's CTE drift. Route-grouped holdout confirms gain on Mach-E and IONIQ-5; Lightning passes through V1 (holdout showed affine hurt it).

## v1_combined
- dir: models/v1_combined/
- structure: differs-from-v1
- status: shelved
- pooled-yaw-rmse-dev: 0.005813
- pooled-cte-rmse-dev: 54.47
- verdict: 3-param per-platform (s, b, k_ff) — identical pooled KPIs to the 2-param affine; k_ff term is statistically redundant. Shipped the simpler `v1_affine` instead.

## dynamic_single_track
- dir: models/dynamic_st/
- structure: differs-from-v1
- status: not-built
- pooled-yaw-rmse-dev: pending
- pooled-cte-rmse-dev: pending
- verdict: Not built. Rung-1 dynamic single-track ODE with cornering stiffness was on the alternatives list; abandoned for time. Most painful absence: no rung-1 scaffold in `_shared/` to start from.
