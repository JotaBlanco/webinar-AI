# Final model — agent-09

Shipped: kinematic single-track + linear understeer + first-order yaw lag + platform-gated per-segment δ₀, with Mach-E L_eff constrained to [2.5, 3.5] m to break g↔L_eff scale invariance.

Pooled metrics on `data/sim/segments/`: yaw_rate_rmse = 0.005820 rad/s (−55.0% vs V0), cte_rmse = 57.04 m (−65.2% vs V0).

Platforms supported: Lightning, Mach-E, IONIQ-5, Tesla (V0 passthrough).

See `../REPORT.md` for the full writeup including the rung-1 climb attempt (E03, not shipped).
