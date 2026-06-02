# v1-refit

## Formulation

Identical state-space to V1 (kinematic-single-track + understeer + first-order
lag + per-segment δ₀). Coefficients re-fit on the local sim/ data with a
nonlinear least-squares loop on yaw RMSE.

## Why this exists

m3.v2 lesson: re-fitting V1's coefficients on a different data slice doesn't
move the canonical KPIs by more than basis points. This candidate exists to
confirm that the canonical V1 ship is at the ceiling of its *shape*, so any
gain you do see has to come from a structurally different formulation.

## Status

Not actually refit in this run — preflight tag is `status: shelved`. V1
coeffs are already cohort-validated to 3 decimal places (m3.v2 evidence).
The differs-from-v1 candidate (v1-plus-residual) is what we ship.
