# REPORT — agent-03 final-model (residual_gb)

See `../REPORT.md` for the full report.

**Shipped:** V1 + per-platform `HistGradientBoostingRegressor` over `[delta, d_delta, v, yr_v0, yr_v1, v·yr_v0, a_long]`. Per-platform GB heads stored as `Lightning.pkl`, `MachE.pkl`, `Ioniq.pkl`. Tesla = V0 passthrough.

**Pooled dev (sim/segments):** yaw 0.00743 rad/s (-30.0% vs V1), CTE 59.44 m (-21.4% vs V1).

Held-out (route-grouped 80/20 per platform): yaw 2-13% better than V1, CTE 14-51% better — generalises out of route.
