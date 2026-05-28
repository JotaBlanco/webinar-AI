# Research — lateral-fidelity challenge

## Problem framing

Task: improve lateral predictions of KS model and attribute each improvement.

- Truth: Ford only (`yaw_rate_meas_rads`, `a_lat_meas_mps2`).
- Predicted: `yaw_rate_pred_rads`, `a_y_pred_mps2`.
- Residual sign convention: `pred − meas` (column already computed).
- KS lateral-only mode: `v` and `δ` clamped to measured; only lateral states (yaw, yaw-rate, a_y, x, y) are predicted.
- Score: RMSE of `yaw_rate_resid_rads` (overall + per-regime: straight / steady / transient).

## V0 baseline (from evals/baseline_rmse.py)

FORD_MUSTANG_MACH_E_MK1 (315 segments, 913,626 samples)
- overall: 0.01613
- straight: 0.00877
- steady: 0.03173
- transient: 0.05680

FORD_F_150_LIGHTNING_MK1 (230 segments, 667,141 samples)
- overall: 0.02037
- straight: 0.00899
- steady: 0.03617
- transient: 0.05190

The error grows monotonically straight → steady → transient — classical KS failure mode: it can't represent the slip-angle dynamics that drive transient yaw response. Steady error is dominated by neutral-steer kinematic gain mismatch (true vehicle understeers); transient by missing tyre lag.

## Plausible failure modes

1. Constant zero-offset (sensor / mounting): trivial bias.
2. Steering gain mismatch: openpilot steer-ratio + tire pressure / scrub: kinematic gain `v·tan(δ)/L` is wrong.
3. Time lag between measured δ and measured ψ̇: KS responds instantly; real vehicle integrates through tyres → lag.
4. Per-segment IMU offset: each route may have its own constant bias from mounting; per-segment fit memorises this.

## Skills to load

- `baseline-residual` already used (V0).
- `ablation-study` will drive the ladder (interleaved 5-th-sample test split, marginal accounting, coherence ≤ 15%).

## Operating contract restated

KS lateral-only, clamped v and δ. We may not change `delta_road_rad` semantics, but we may post-correct `yaw_rate_pred_rads` per the variant under test. `a_y_pred` is downstream of ψ̇ — out of scope for this challenge (yaw-rate channel only).
