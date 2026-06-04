# Final model — agent-06

Shipped: kinematic single-track + linear understeer + first-order yaw lag + platform-gated per-segment δ₀.

Pooled metrics on `data/sim/segments/`: yaw_rate_rmse = 0.005874 rad/s (−54.6% vs V0), cte_rmse = 56.81 m (−65.3% vs V0).

Coefficients from `references/anti-patterns.md` § "Legal cousin". Platforms supported: Lightning, Mach-E, IONIQ-5, Tesla (V0 passthrough).

See `../REPORT.md` for the full writeup including the rung-1 climb attempt (V4, rejected).
