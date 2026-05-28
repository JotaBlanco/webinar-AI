# Research — 20260527-155834

## Setting

- Platform scored: **FORD_MUSTANG_MACH_E_MK1** (the Mustang Mach-E MK1 has
  decoded IMU truth channels `yaw_rate_meas_rads` and `a_lat_meas_mps2`; the
  Lightning does too but the Mach-E has the larger segment set: 315 vs 230).
- Number of segments: 315 sim CSVs under `data/sim/segments/FORD_MUSTANG_MACH_E_MK1/`.
- Number of samples: ~315 × ~600 ≈ 1.9 × 10^5 at 50 Hz (confirmed during impl).

## Operating contract restated

- **Clamped** (model inputs): `v_mps`, `delta_road_rad`. The KS integrator's
  internal `v` and `δ` state are overwritten by the measured channels every
  step (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`).
- **Predicted** (channels under test): `yaw_rate_pred_rads`, `a_y_pred_mps2`.
- **Residual under test**: `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads`
  (lateral-only; speed-state agreement is zero by construction and is not the
  metric).

## Baseline (V0) — no preprocessing

To be filled in by `tools/eval_lateral.py`. Regime definitions (from
`vehicle-dynamics-rlog`):

- Straight: `|δ_road| < 0.01` rad.
- Steady cornering: `|δ_road| ≥ 0.01` and `|dδ/dt| < 0.05` rad/s.
- Transient cornering: `|δ_road| ≥ 0.01` and `|dδ/dt| ≥ 0.05` rad/s.

## Sign-convention sanity

- `corr(delta_road_rad, yaw_rate_meas_rads)` on cornering samples — expected
  positive. Negative would indicate a sign error upstream; reported in
  `out/lateral_eval.json`.

## Plausible failure modes

1. **Per-segment IMU yaw-gyro offset** soaking into straight-line bias. KS
   cannot correct a sensor offset; a per-segment mean on straights is the
   cheapest soaker.
2. **KS has no slip**: at high `|a_y|`, the lateral force balance the linear
   ST model captures (understeer gradient `K_us`) is missing from KS. This
   should show as a systematic high-`|δ|` residual.
3. **Wrong cornering stiffnesses**: even an ST model only helps if its `C_α`
   priors match the actual tyres. The openpilot canonical values are a prior,
   not a calibration — refitting may help, *or* may peg the bound (regression
   flag: linear-ST form itself is wrong).
4. **Sign error at adapter layer**: a flipped CAN signal would invalidate
   everything; we check sign sanity before scoring.

## Open questions

- Is the high-`|a_y|` residual symmetric in turn direction? (left vs right)
- Does V3 peg `C_αf` at the 500-kN upper bound, indicating the linear-ST gain
  form is the wrong shape for these tyres at scored speeds?

## Wishlist (post-mortem)

- Pacejka tyre model for V4 — out of scope at 15-min budget.
- Per-segment Ridge LOSO residual learner — only honest with LOSO CV.
