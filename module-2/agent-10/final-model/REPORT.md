# final-model/REPORT.md — agent-10

V3 kinematic-bicycle predictor with per-platform calibration. See top-level
REPORT.md in the agent directory for the full writeup.

## Numbers (pooled across 1996 segments in data/sim/segments)

- yaw_rate_rmse: 0.006059 rad/s  (V0 baseline: 0.012934 rad/s) — 53.2% reduction
- cte_rmse:      80.42 m         (V0 baseline: 163.83 m)      — 50.9% reduction

Tesla passes through V0 (its truth channel IS the V0 KS output per
PLATFORM_SCHEMA).
