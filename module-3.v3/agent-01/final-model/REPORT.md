# final-model/REPORT.md — bias-corrected-v1

Bundle-internal report stub for the preflight check.

## Shipped model
**bias-corrected-v1** — V1 + per-platform additive yaw-rate offset.

Yaw offsets (rad/s):
- FORD_F_150_LIGHTNING_MK1: 0.0
- FORD_MUSTANG_MACH_E_MK1: +0.00210
- HYUNDAI_IONIQ_5: +0.00108
- TESLA_MODEL_3: 0 (V0 passthrough)

## Pooled dev scores (data/sim/segments/, all platforms)
| metric | V1 floor | bias-corrected-v1 | Delta |
|---|---|---|---|
| yaw_rate_rmse (rad/s) | 0.005874 | 0.005843 | -0.5% |
| cte_rmse (m)          | 56.807   | 54.189   | -4.6% |

## Rationale
V1 leaves persistent signed yaw bias on Mach-E (-0.00142 rad/s) and IONIQ-5 (-0.00075 rad/s) that integrates into CTE drift (-22 m, -12 m). Killing the bias with a fitted per-platform constant on V1's output drops pooled CTE 4.6%.

## Alternatives shelved
- steering-derivative-residual: yaw 0.005827 / CTE 54.51
- v-dependent-lag: yaw 0.005871 / CTE 56.74 (effectively V1)
