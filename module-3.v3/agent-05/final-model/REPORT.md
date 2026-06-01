# Final model — V1 (Rung 0, refined)

Shipped model is V1: kinematic single-track + steady-state understeer + first-order yaw lag + platform-gated per-segment δ₀.

Headline (scored over all 1996 segments in `data/sim/`):
- yaw_rate_rmse: 0.005874 rad/s (V0 baseline: 0.012934 → -54.6%)
- cte_rmse: 56.81 m (V0 baseline: 163.83 → -65.3%)

See ../REPORT.md for the full writeup and ../EXPERIMENTS.md for the log including the required Rung 1 attempt (E03).
