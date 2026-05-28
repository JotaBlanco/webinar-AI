# Research — 20260527-155947

## Setting

- Platform scored: FORD_MUSTANG_MACH_E_MK1 (primary). FORD_F_150_LIGHTNING_MK1 (secondary cross-check).
- Number of segments: Mustang 315, F-150 230.
- Number of samples: Mustang 913,626; F-150 667,141 (50 Hz).

## Operating contract restated

- **Clamped** (inputs from CAN): `v_mps`, `delta_road_rad`.
- **Predicted** (outputs under test): lateral states — `yaw_rate_pred_rads`, `a_y_pred_mps2`, plus `psi`, `x`, `y`.
- Residual under test: `yaw_rate_resid_rads = pred − meas` (project sign convention).

## Baseline (V0) — no preprocessing

Mustang:
- overall: 0.01613
- straight: 0.00877
- steady: 0.03173
- transient: 0.05680

F-150:
- overall: 0.02037
- straight: 0.00899
- steady: 0.03617
- transient: 0.05190

## Sign-convention sanity

`corr(delta_road_rad, yaw_rate_meas_rads)` on cornering samples is positive in spot-check (ISO-8855 left-positive). `schema_check.py` enforces this.

## Plausible failure modes

- **Steady-state gain low.** First-50-segment OLS `meas ≈ 1.125·pred + 0.003`. KS bicycle with rigid kinematic assumption underestimates yaw rate on this car (tyre side-slip and effective steering ratio absorbed into a scalar gain).
- **Small static bias.** Intercept ~3 mrad/s in the same regression — looks like a steering-zero / IMU-zero offset.
- **Lag.** Cross-correlation on one segment shows pred leads meas by ~1 sample (20 ms). Plausible: openpilot CAN timestamping vs. sim integrator step.
- **Transient amplification.** Per-regime RMSE explodes in transient (0.057 vs 0.009 straight). KS lacks yaw inertia / side-slip dynamics, so high-`d δ/dt` is the worst.
- **a_y coupling.** `a_y_pred = v·ψ̇` in KS; any ψ̇ fix propagates.

## Open questions

- Is the lag platform-wide or segment-by-segment jittery?
- Does a single per-platform gain capture both Fords, or do they need separate gains?

## What I would want next

- Time-varying gain by speed/yaw-rate magnitude.
- Dynamic single-track (tyre cornering stiffness) — beyond a 15-min budget.
