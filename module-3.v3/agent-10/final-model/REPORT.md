# final-model — v1-plus-resid

Shipped model: per-platform linear residual learner on top of the V1 kinematic-single-track baseline.

## Pooled dev scores (data/sim/segments, 1996 segments, ~5.2 M samples)

| metric | V1 | v1-plus-resid | Δ vs V1 |
|---|---|---|---|
| yaw_rate_rmse (rad/s) | 0.005874 | **0.005727** | −2.5% |
| cte_rmse (m)          | 56.807   | **54.304**   | −4.4% |

## Per-platform

| platform | yaw V1 | yaw shipped | CTE V1 | CTE shipped |
|---|---|---|---|---|
| FORD_F_150_LIGHTNING_MK1 | 0.00566 | 0.00550 | 62.19 | 65.40 |
| FORD_MUSTANG_MACH_E_MK1  | 0.00859 | 0.00815 | 98.68 | 90.38 |
| HYUNDAI_IONIQ_5          | 0.00766 | 0.00755 | 69.53 | 66.97 |
| TESLA_MODEL_3            | 0       | 0       | 0     | 0     |

See `models/v1-plus-resid/notes.md` and `assessment.md` for the formulation,
fit procedure, and residual diagnosis.
