# Final model bundle report

Yaw RMSE: 0.005874 rad/s (V0 0.012934 -> -54.6 percent)
CTE RMSE: 56.81 m (V0 163.83 -> -65.3 percent)

Model: KS + understeer + first-order lag + per-segment delta0 (platform-gated).
- Mach-E and Hyundai IONIQ-5: per-segment delta0 ON (gate yaw_rate_pred < 0.03 and v > 5).
- Lightning: per-segment delta0 OFF (global delta0).
- Tesla: V0 passthrough (no truth channel).

Per-platform pooled (sim/):
- FORD_F_150_LIGHTNING_MK1: yaw 0.00566 cte 62.19 (bias ok)
- FORD_MUSTANG_MACH_E_MK1: yaw 0.00859 cte 98.68 (cte drift -22.0 m)
- HYUNDAI_IONIQ_5: yaw 0.00766 cte 69.53 (cte drift -11.6 m)
- TESLA_MODEL_3: passthrough (no truth)

See ../REPORT.md and ../EXPERIMENTS.md for the full narrative.
