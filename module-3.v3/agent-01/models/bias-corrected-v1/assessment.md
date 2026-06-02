# Assessment — bias-corrected-v1

## Pooled dev scores
- yaw_rate_rmse: **0.005843 rad/s** (V1: 0.005874 → −0.5%)
- cte_rmse:      **54.189 m** (V1: 56.807 → **−4.6%**)

## Per-platform (yaw / CTE / signed bias / signed drift)
| platform | yaw RMSE | CTE RMSE | yaw bias | CTE drift |
|---|---|---|---|---|
| Lightning | 0.00566 | 62.18 | +0.00012 | +0.32 |
| Mach-E    | 0.00850 | **91.26** (V1 98.68 = −7.5%) | +0.00068 | +2.76 |
| IONIQ-5   | 0.00763 | **67.03** (V1 69.53 = −3.6%) | +0.00033 | +0.58 |
| Tesla     | 0       | 0    | 0       | 0     |

## Residual diagnosis after correction
The per-platform signed CTE drift moved from {Lightning +0.3, Mach-E −22.0, IONIQ −11.6} to {+0.3, +2.8, +0.6}. The Mach-E and IONIQ CTE drifts are now below the 5 m warning threshold; the bias-correction worked as predicted.

The remaining CTE pool (54 m) is dominated by **route-level un-correlated yaw noise**, not bias. Killing that requires structural changes (steering-derivative residual, dynamic single-track) which produced no further pooled gain (see other candidates).

## Verdict
**Ship.** Clean structural attack on V1's residual; pooled CTE −4.6%, pooled yaw essentially unchanged. Risk surface tiny (2 scalars added). The model preserves V1's stability and Tesla passthrough.
