# Final-model bundle notes (V1)

## Headline
- **yaw_rate_rmse: 0.00608 rad/s** (-55% vs V0 baseline 0.01361)
- **cte_rmse: 55.85 m** (-66% vs V0 baseline 163.83)

## Per-platform pooled (full 1996-segment set)

| platform | yaw_rmse | dy/V0 | cte_rmse | dc/V0 |
|---|---|---|---|---|
| FORD_F_150_LIGHTNING_MK1 | 0.00597 | -63% | 60.83 | -61% |
| FORD_MUSTANG_MACH_E_MK1  | 0.00863 | -37% | 98.70 | -33% |
| HYUNDAI_IONIQ_5          | 0.00800 | -55% | 67.61 | -73% |
| TESLA_MODEL_3            | 0.00000 | (passthrough; no truth) | 0.00 | (passthrough) |

## Model shape
Per-platform kinematic single-track + understeer + first-order lag, with
per-segment delta0 from the straight-row median (gate: |yr_v0|<0.03 AND v>5).
Lightning uses static delta0; Mach-E + IONIQ-5 use per-segment delta0; Tesla
passes through V0 (no truth channel to fit against).

See `coeffs.json` for fitted per-platform parameters.
See `../EXPERIMENTS.md` for the full log, including a rung-1 attempt
(linear dynamic single-track; reverted because rung 0 + per-segment delta0 wins).
