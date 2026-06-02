# Assessment — affine-postcorrection

## Local dev scores (sim-only/segments/)

| platform | yaw RMSE | CTE RMSE | signed CTE mean |
|---|---|---|---|
| Lightning | 0.01269 (-0.3%) | 62.05 (-0.2%) | -3.97 |
| Mach-E    | 0.01341 (-1.6%) | 91.59 (-7.2%) | -1.87 |
| IONIQ-5   | 0.00889 (-0.4%) | 67.54 (-2.9%) | -4.20 |
| **POOLED** | **0.01053 (-0.7%)** | **72.53 (-4.1%)** | — |

Reference V1: yaw 0.01061, CTE 75.65.

## Residual character after correction
- All signed CTE biases reduced from |10-22| m down to |2-4| m. Bulk shift removed.
- Yaw RMSE barely moves: most residual is high-frequency noise, not bias.
- Remaining residual is structural high-|a_lat| tyre saturation (Mach-E) — orthogonal to this correction.

## Verdict: KEEP. Most of the CTE win comes from this single bias term per platform.
