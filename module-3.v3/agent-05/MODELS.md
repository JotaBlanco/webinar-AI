# MODELS.md — registry of candidate models

V1 pooled-dev: yaw_rmse = 0.005874 rad/s, cte_rmse = 56.81 m.

## v1-baseline
- dir: models/v1-baseline/
- structure: refines-v1
- status: assessed
- pooled-yaw-rmse-dev: 0.00587
- pooled-cte-rmse-dev: 56.81
- verdict: reference floor. Not the ship candidate — competitors are graded against this.

## v1-debiased
- dir: models/v1-debiased/
- structure: differs-from-v1
- status: shipped
- pooled-yaw-rmse-dev: 0.00584
- pooled-cte-rmse-dev: 54.19
- verdict: SHIP. Per-platform additive yaw-bias correction. Targets the residual CTE drift that V1 leaves on Mach-E (-22 m) and IONIQ-5 (-12 m). Pooled CTE -4.6%; Mach-E CTE -7.5%. Small win, but the only structural attack that paid out within budget.

## v1-debiased-kdd
- dir: models/v1-debiased-kdd/
- structure: differs-from-v1
- status: shelved
- pooled-yaw-rmse-dev: 0.00584
- pooled-cte-rmse-dev: 54.19
- verdict: SHELVE. Adds k_dd * d(delta)/dt on top of v1-debiased. Grid-search optimum gain is essentially zero — V1's first-order lag has already absorbed the transient signal that a linear-in-steering-rate correction could extract. Negative result that points at the rung-1 dynamic-bicycle ODE as the next thing to try (not built in budget).
