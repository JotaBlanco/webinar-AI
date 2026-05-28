# Research — `rpi/runs/20260527-155851/research.md`

## Setting

- Platform scored: **FORD_MUSTANG_MACH_E_MK1** (Ford — has measured truth `yaw_rate_meas_rads`, `a_lat_meas_mps2`. Tesla excluded per skill: no IMU truth.)
- Number of segments: 80 (capped from 315 to keep within 15-min budget; same set fixed across all variants)
- Number of samples: 231,926 (50 Hz, dt=0.02 s)

## Operating contract restated

- Clamped (inputs): `v_mps`, `delta_road_rad` — speed-known, lateral-only.
- Predicted (output under test): `yaw_rate_pred_rads` (KS: `(v/L)·tan(δ)`).
- Residual under test: `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads`, scored by RMSE.

## Baseline (V0) — `yaw_rate_resid_rads` as-is

| regime | RMSE [rad/s] | N |
|---|---:|---:|
| overall | 0.01190 | 231,926 |
| straight (`\|δ\| < 0.01`) | 0.00853 | 211,404 |
| steady cornering (`\|δ\| ≥ 0.01, \|dδ/dt\| < 0.05`) | 0.02331 | 17,635 |
| transient cornering (`\|δ\| ≥ 0.01, \|dδ/dt\| ≥ 0.05`) | 0.05224 | 2,887 |

## Sign-convention sanity

- `corr(delta_road_rad, yaw_rate_meas_rads)` on cornering samples = **+0.9087**. ISO 8855 left-positive holds. No sign flip needed.

## Plausible failure modes (enumerate, do not fix yet)

1. **IMU yaw-gyro bias / per-segment offset** on straight-line samples. Straight RMSE 8.5 mrad/s is large relative to a typical gyro bias of a few mrad/s; might soak up.
2. **No slip in KS.** Steady-cornering residual (23.3 mrad/s) and transient (52.2 mrad/s) are what an ST upgrade *could* close.
3. **Prior `C_α` mismatch.** openpilot priors are sticky-tyre; real Mach-E may be softer. ST with fit `C_α` may help where ST-prior does not.
4. **Steering-actuation latency.** `δ_road` and `ψ̇` may be on slightly offset time bases; a few-step lag could blow up the transient RMSE without affecting steady.
5. **Low-`v` ST blow-up.** ST gain `1/(L(1+K_us·v²))` is fine, but the dynamic ST has eigenvalues `~(Cαf+Cαr)/(m·v)` — must guard with `v_min ≈ 2 m/s`.

## Open questions

- What fraction of straight-line residual is gyro bias vs road camber / sloshing?
- Does a fit-`C_α` ST peg at the upper bound? (regression flag for non-linear tyre, not just prior mismatch)

## Wishlist (for post-mortem)

- Cross-platform check: does the same ladder behave the same way on the F-150 Lightning?
- Per-segment temperature / tyre-pressure metadata to explain residual scatter.
- LOSO ML residual learner as a final rung (out of budget today).
