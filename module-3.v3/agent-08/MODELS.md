# MODELS.md — registry of candidate models

V1's pooled-dev scores for comparison: `yaw_rmse = 0.00762 rad/s`, `cte_rmse = 75.65 m`
(local scorer on full `data/sim/segments/` across the three truth platforms,
yaw filtered `v_mps > 2`).

---

## v1-plus-residual
- dir: models/v1-plus-residual/
- structure: differs-from-v1
- status: shipped
- pooled-yaw-rmse-dev: 0.00738
- pooled-cte-rmse-dev: 71.77
- verdict: ship. Linear per-platform additive residual on allowlist features beats V1 by 3.1% yaw / 5.1% CTE pooled. Lightning CTE regresses slightly (+3%); net win on every other cell.

## v1-refit
- dir: models/v1-refit/
- structure: refines-v1
- status: shelved
- pooled-yaw-rmse-dev: not-run
- pooled-cte-rmse-dev: not-run
- verdict: shelved. Cohort already converged V1 coeffs to 3 decimals; refit expected to move metrics by <1%. Time better spent elsewhere.

## dynamic-single-track
- dir: models/dynamic-single-track/
- structure: differs-from-v1
- status: drafting
- pooled-yaw-rmse-dev: not-run
- pooled-cte-rmse-dev: not-run
- verdict: drafted (formulation in notes.md, predict falls through to V1). The cheaper residual-learner ate the time budget; recommend a future agent picks this up to attack Mach-E transient regime.
