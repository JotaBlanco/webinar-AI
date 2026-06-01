# final-model - m3v2 agent-04

See ../REPORT.md for the full writeup. Shipped: rung-0 KS + understeer + first-order lag + platform-gated per-segment delta0 (Mach-E + IONIQ-5 on, Lightning off). Tesla passthrough V0.

Pooled headline (scored via skills/score-model over all data/sim/segments):
- yaw_rate_rmse = 0.005824 rad/s  (V0 0.012934 -> -55.0%)
- cte_rmse      = 57.05 m         (V0 163.83  -> -65.2%)

Files:
- predict.py   - predict callable.
- coeffs.json  - per-platform fitted coefficients.
- manifest.json - declares platform_support and predict_callable.

Coefficients fit on data/sim/ with route-grouped 75/25 train/dev split (seed 0), Nelder-Mead, objective pooled yaw-rate RMSE per platform.
