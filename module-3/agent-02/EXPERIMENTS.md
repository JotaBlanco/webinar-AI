# EXPERIMENTS.md

## E00 — V0 baseline (pass-through)
- Hypothesis: establish the floor.
- Result (dev, all 4 platforms): yaw 0.009450; CTE 163.83.
- Per-platform bias: Ford F-150 +0.00411 (cte +39.7 m, 🚨), Mustang -0.00040 (ok),
  Hyundai -0.00362 (cte -54.8 m, 🚨), Tesla 0 (truth==baseline).
- Verdict: baseline.

## E01 — Per-platform understeer: yaw = alpha * V0 / (1 + K*v^2)
- Hypothesis: the per-platform yaw bias and the v² growth in CTE drift point to a
  classic understeer-gradient miscalibration of the kinematic V0.
- What I changed: 1-D Brent over K, closed-form alpha by OLS, per platform.
- Result: Ford F-150 yaw 0.0163→0.0075; Mustang 0.0136→0.0091; Hyundai 0.0177→0.0089.
- Verdict: keep.
- Rules out: the bias is dominantly a *gain* problem, not a sign-of-steering one.

## E02 — Add a constant offset: yaw = alpha * V0 / (1 + K*v^2) + beta — SHIPPED
- Hypothesis: residual signed bias after E01 (esp. Ford F-150 -0.0044) is a fixed
  yaw-gyro/installation offset; cheap to fit, kills CTE drift.
- What I changed: OLS for (alpha, beta) inside the Brent search over K.
- Result (pooled): yaw 0.009450 → 0.006511 (-31%); CTE 163.83 → 79.90 (-51%).
  All bias warnings cleared.
- Verdict: ship.

## Not pursued (time budget)
- E03 dynamic single-track (cornering stiffness, slip angles) — structural rung up.
  Would primarily help transient regime (rmse 0.0192 even after E02), but tuning
  Cf, Cr, Iz per platform without a train/dev split risks overfitting.
- E04 residual learner (linear in v, delta_road, delta_dot, lat-accel) — skipped:
  no make-train-dev-split discipline applied, single-eval risk.

## Approach short-list (named up front)
1. Constant scale on V0.
2. Understeer formula (picked, E01/E02).
3. Affine OLS in (V0, V0·v², 1).
4. Dynamic single-track (structural rung up).
5. Residual MLP on (V0, v, δ).
Structurally different: V0-algebra (1/2/3), dynamic-bicycle (4), data-driven (5).
