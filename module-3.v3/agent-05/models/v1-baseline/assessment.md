# v1-baseline — assessment

**Verdict**: reference model. Used as the floor for candidate comparison.

| platform | yaw RMSE | CTE RMSE | cte_signed |
|---|---|---|---|
| FORD_F_150_LIGHTNING_MK1 | 0.00566 | 62.18 | +0.32 |
| FORD_MUSTANG_MACH_E_MK1 | 0.00859 | 98.68 | -21.98 |
| HYUNDAI_IONIQ_5 | 0.00766 | 69.53 | -11.57 |
| TESLA_MODEL_3 | 0 | 0 | 0 |
| **pooled** | **0.00587** | **56.81** | — |

Mach-E and IONIQ-5 carry the bulk of CTE error, and on both the signed CTE drift dominates RMSE.
That's a yaw-bias signature, which suggests a constant additive correction can claw back meters of CTE.
