# Research — `rpi/runs/20260527-155852/research.md`

## Setting

- Platform scored: `FORD_MUSTANG_MACH_E_MK1` (most segments, has yaw_rate_meas + a_lat_meas truth channels; Tesla excluded per skill — IMU not decoded).
- Number of segments: 80 (deterministic stride from 315 available sim.csv, to keep RPI run under 15 min budget).
- Number of samples: 232 017 raw, 203 303 after `v >= 2 m/s` (KS singularity / regime undefined at sub-walking speed).

## Operating contract restated

- Clamped (inputs): `v_mps` and `delta_road_rad` (set in `simulate_ks` with `clamp_v_to_measured=True`, `clamp_delta_to_measured=True`).
- Predicted (output under test): `yaw_rate_pred_rads` (and `a_y_pred_mps2`).
- Residual under test: `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` (pre-computed in CSV). Lateral-only.

## Baseline (V0) — no preprocessing

- Overall RMSE on `yaw_rate_resid_rads`: **0.01451 rad/s**.
- Per regime (definitions below):
  - Straight  (`|δ_road| < 0.01`): 0.00890
  - Steady    (`|δ_road| ≥ 0.01`, `|dδ/dt| < 0.05`): 0.02706
  - Transient (`|δ_road| ≥ 0.01`, `|dδ/dt| ≥ 0.05`): 0.04893

## Sign-convention sanity

- `corr(delta_road_rad, yaw_rate_meas_rads)` on cornering samples: **+0.934**. Positive — sign convention is consistent end-to-end, no sign flip needed.

## Plausible failure modes (enumerated, not yet fixed)

- IMU yaw-gyro bias: non-zero mean of `yaw_rate_resid` on straight samples per segment — pure offset that KS cannot model and that an ST upgrade cannot soak up either.
- KS has no slip; high-`|a_y|` transient/steady residual is the structural KS gap. A linear-ST upgrade *might* close it if openpilot prior `C_α` matches the tyres.
- openpilot prior `C_α` for Mach-E (286k front / 356k rear) is *front-soft / rear-stiff*, which is what produces the K_us > 0 understeer of the prior. If real car is closer to neutral, ST steady-state gain *under*-predicts and would *regress* vs KS geometric tan(δ).
- Steady-state ST gain ignores yaw-rate transient dynamics — would be visibly worse on the transient regime than on steady.

## Open questions

- Will straight-line residual mean look like a per-segment offset (IMU bias) or a per-segment drift (calibration trend)?
- Does the LOSO C_α fit *peg* against the 500k upper bound (regression flag per skill)?

## What I would want next (wishlist, post-mortem)

- Per-segment data on road grade / banking — a banked highway sample would have a steady non-zero `yaw_rate_meas` on what we class as "straight".
- A second IMU channel to disambiguate gyro bias from yaw drift integrated from gyro noise.
