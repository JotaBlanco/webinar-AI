# Assessment — v-dependent-lag

## Pooled dev scores
- yaw_rate_rmse: **0.005871 rad/s** (V1: 0.005874 → −0.05%, noise)
- cte_rmse:      **56.741 m** (V1: 56.807 → −0.1%, noise)

## Per-platform
| platform | yaw RMSE | CTE RMSE |
|---|---|---|
| Lightning | 0.00566 (V1 0.00566) | 62.18 |
| Mach-E    | 0.00860 (V1 0.00859) | 98.64 |
| IONIQ-5   | 0.00766 (V1 0.00766) | 69.39 |

## Residual diagnosis
The grid-search optimum collapsed Mach-E and Lightning back to τ1 = 0 (pure V1 lag). Only IONIQ-5 picked up a non-trivial τ1 = 0.05, with a marginal RMSE win of 0.0001 — below the noise floor of cross-fold variability.

## Verdict
**Shelve.** This rules out "scalar lag is the bottleneck" as a hypothesis. The lag time-constant is already well-fit for sample-weighted RMSE; the residual is *not* mostly in transient lag mis-modelling. The persistent yaw bias and route-noise account for the rest of V1's gap to ground truth.

Useful negative result: the dynamic-single-track motivation (rung-1 in dynamics-formulations.md) is *not* what V1 needs. Don't climb that rung.
