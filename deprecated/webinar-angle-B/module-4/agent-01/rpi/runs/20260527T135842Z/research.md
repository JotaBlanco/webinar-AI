# Research — 20260527T135842Z

## Setting

- Platform scored: FORD_MUSTANG_MACH_E_MK1 (Ford — only platform with truth `ψ̇` and `a_y`; Tesla has no IMU truth)
- Number of segments: 60 (subset of 315, time budget; same set across all variants)
- Number of samples: see `out/ladder.json` (~60 segments × ~60 s × 50 Hz ≈ 180k samples)

## Operating contract restated

- Clamped (inputs): `v_mps`, `delta_road_rad` (KS run with `clamp_v=True`, `clamp_delta=True`)
- Predicted (outputs under test): `yaw_rate_pred_rads`, `a_y_pred_mps2`
- Residual under test: `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` (lateral only). Speed agreement is zero by construction and is not the metric.

## Baseline (V0)

- See `out/ladder.json` — `table_rmse.V0_baseline`.
- Regimes (fixed mask, applied identically every rung):
  - straight: `|delta_road| < 0.01`
  - steady cornering: `|delta_road| ≥ 0.01` ∧ `|dδ/dt| < 0.05`
  - transient cornering: `|delta_road| ≥ 0.01` ∧ `|dδ/dt| ≥ 0.05`

## Sign-convention sanity

- `corr(delta_road_rad, yaw_rate_meas_rads)` on cornering samples: reported in `out/ladder.json` (`sign_corr_corn_delta_yawmeas`); must be positive.

## Plausible failure modes (enumerated, not yet fixed)

- IMU yaw-gyro bias: KS predicts ~0 yaw rate on straight; truth has DC offset → constant residual per segment.
- KS lacks tyre slip: residual grows with `|a_y|` (understeer / lateral compliance) — ST upgrade is the canonical next rung.
- Cornering stiffness priors are openpilot's `carParams`, possibly mis-calibrated for these tyres/roads — fit may help, pegging at bound = ST form itself wrong.
- Steering-ratio/sign errors already vetted (sim CSV ships `delta_road_rad` post-conversion).
- High-|δ| samples may exceed the linear-tyre regime — ST will degrade in transients; flagged as a possible regression rung.

## Open questions

- Are the few segments where the per-segment bias is huge actually dominated by curb-tilt/banking rather than IMU offset?
- LOSO ridge on `[v, |a_y|, |δ|, sign(δ̇)]` — does it earn its drop, or just memorise drivers?

## Wishlist for the post-mortem

- IMU temperature/cold-start metadata to separate bias from drift.
- A road-banking channel; the unexplained DC residual on straight, cambered roads is the most embarrassing artefact.
