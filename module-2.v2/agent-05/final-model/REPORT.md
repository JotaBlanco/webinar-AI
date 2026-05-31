# Final-model report — idea-01 lateral fidelity

See the top-level REPORT.md (/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-05/REPORT.md) for the full write-up.

## Headline
Per-platform OLS correction of the V0 KS yaw rate with a 12-term polynomial
basis in (yaw_v0, v, delta_road, steer_rate, a_long). TESLA_MODEL_3 passes
V0 through unchanged because its only "truth" channel IS V0 (psi_dot_rads).

Trajectory (x, y) is integrated downstream of the corrected yaw rate using
the same zero-order-hold Euler convention as `_shared/traj_metrics.py`.

## Local pooled KPIs (data/sim/segments, all platforms)
- V0 baseline:   yaw_rate_rmse = 0.012934 rad/s, cte_rmse = 163.83 m
- V3 (shipped):  yaw_rate_rmse = 0.006251 rad/s, cte_rmse =  78.71 m

## Files
- predict.py  — predict(sim_df, platform) -> DataFrame
- coeffs.json — per-platform fitted coefficients
- manifest.json
