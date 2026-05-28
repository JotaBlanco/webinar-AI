# Research — 20260527-160000

## Setting
- Platform scored: FORD_MUSTANG_MACH_E_MK1 (primary), FORD_F_150_LIGHTNING_MK1 (secondary cross-check).
- Number of segments: 315 (Mach-E), 230 (Lightning).
- Number of samples: 913,626 (Mach-E), 667,141 (Lightning).

## Operating contract restated
- Clamped (inputs): `v_mps`, `delta_road_rad` (clamp_v_to_measured + clamp_delta_to_measured).
- Predicted (outputs under test): yaw rate `ψ̇` and `a_y = v·ψ̇` (coupled).
- Residual under test: `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` (rule 1: pred − meas).

## Baseline (V0) — no preprocessing
- Mach-E overall RMSE: 0.01613 rad/s.
  - straight: 0.00877  | steady: 0.03173  | transient: 0.05680
- Lightning overall RMSE: 0.02037 rad/s.
  - straight: 0.00899  | steady: 0.03617  | transient: 0.05190

## Sign-convention sanity
- corr(δ_road, ψ̇_meas) on cornering samples: positive on both platforms (schema_check passes on the raw sim CSV).

## Plausible failure modes (enumerate, not fix)
- Constant yaw-rate sensor zero-offset (gyro bias) inflating straight-line RMSE.
- Per-segment IMU bias accumulating after each ignition cycle (sensor calibration, not model).
- Steering-ratio / wheel-to-road conversion gain wrong → KS ψ̇ amplitude off in cornering (steady regime).
- KS ignores tire side-slip → understeer gradient unmodelled → transient regime over-predicts ψ̇ at higher v·δ products.
- Time alignment between CAN steering and IMU yaw (latency) → drives transient residual specifically.
- v clamped from wheel speed could be over/underestimated, but v multiplies both sides equally — second-order.

## Open questions
- Is the offset constant per-platform or per-segment? (V1 vs V2 disambiguates.)
- Does a single gain scalar on δ collapse the steady-regime error? (V3.)
- Does affine δ correction also help transient regime, or is that a side-slip phenomenon out of KS's reach? (V4.)

## What I would want next (wishlist)
- A dynamic single-track (ST) rung with cornering stiffness so transient can be properly attacked.
- Held-out routes (different drivers) to verify per-platform gain isn't memorising one ECU's quirks.
