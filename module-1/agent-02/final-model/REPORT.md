# agent-02 — lateral-fidelity submission

## Headline numbers (held-out 40% of segments per platform)

| Platform | Yaw RMSE V0 | Yaw RMSE Final | dCTE V0 | dCTE Final |
|---|---|---|---|---|
| FORD_F_150_LIGHTNING_MK1 (n=70) | 0.01225 rad/s | 0.00547 rad/s (-55%) | 71.8 m | 34.5 m (-52%) |
| FORD_MUSTANG_MACH_E_MK1 (n=96)  | 0.01196 rad/s | 0.00813 rad/s (-32%) | 72.9 m | 62.0 m (-15%) |

dCTE = distance-resampled cross-track-error RMSE, integrated over the full
~58-s segment with (yr_meas, v_meas) as the truth trajectory and
(yr_pred, v_meas) as the predicted trajectory, 1 m arc-length grid,
path-normal offset.

Tesla is not evaluated (no yaw_rate_meas_rads truth in its sim.csv);
the Tesla coefficients in coeffs.json are a sensible prior.

## Fidelity ladder

- V0 - pure KS (baseline in yaw_rate_pred_rads): yr = v*tan(delta)/L.
- V1 - linear-tire understeer: yr_ss = v*delta / (L + K_us*v^2).
- V2 - steering scale + offset: delta_eff = s*delta_road - delta_0.
- V3 - 1st-order yaw lag (tau ~ 50 ms) on yr_ss.

Coefficients fit on a random 60% of segments per platform with
scipy.optimize.least_squares; the other 40% are the held-out pool above.

## Inputs required
t_s, v_mps, delta_road_rad in sim_df.

## Files
- predict.py - entry point predict(sim_df, platform)
- coeffs.json - fitted per-platform coefficients
- manifest.json - declared platform support + callable path
