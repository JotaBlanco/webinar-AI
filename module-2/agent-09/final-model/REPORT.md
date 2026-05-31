# Final Model — V3 per-platform calibrated bicycle

See the module-level REPORT.md for the full writeup.

## Model

    yaw_rate_pred = g * v * delta_road / (L + K * v^2) + b

Fit per platform (offline) on data/sim/segments/.

## Coefficients

| Platform | L (m) | g | b | K |
|---|---|---|---|---|
| FORD_F_150_LIGHTNING_MK1 | 3.700 | 0.9746 | -0.00441 | 0.003823 |
| FORD_MUSTANG_MACH_E_MK1 | 2.984 | 1.1998 | +0.00021 | 0.002873 |
| HYUNDAI_IONIQ_5 | 3.000 | 0.9713 | +0.00198 | 0.003414 |
| TESLA_MODEL_3 | 2.875 | 1.0174 | -0.00002 | 0.000064 |

## Local scores (sim/segments truth)

| Platform | yaw RMSE (rad/s) | CTE RMSE (m) |
|---|---|---|
| FORD_F_150_LIGHTNING_MK1 | 0.00631 | 63.7 |
| FORD_MUSTANG_MACH_E_MK1 | 0.00951 | 121.8 |
| HYUNDAI_IONIQ_5 | 0.00875 | 106.9 |
| TESLA_MODEL_3 | 0.00152 | 5.6 |

Ford+Hyundai pooled: yaw 0.00861 rad/s, CTE 105.2 m. Tesla: yaw 0.00152, CTE 5.6.
