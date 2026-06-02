# final-model/REPORT.md

Stub required by `pre-flighting-final-model`. The substantive report is at the agent-root REPORT.md.

## Shipped model

- Identity: `v1-debiased` (see `models/v1-debiased/`).
- Formulation: `yr_hat = predict_v1(sim_df, platform) + b_platform`.
- Per-platform additive yaw-rate bias (rad/s):
  - FORD_F_150_LIGHTNING_MK1: -0.00012
  - FORD_MUSTANG_MACH_E_MK1: +0.00213
  - HYUNDAI_IONIQ_5: +0.00112
  - TESLA_MODEL_3: 0 (V0 passthrough)
- Structural difference from V1: additive output correction; V1 cannot reach
  this by refitting because its per-segment δ₀ scales the *input* rather than
  offsetting the *output*.

## Local dev pooled scores

| metric | V1 | v1-debiased (shipped) | Δ |
|---|---|---|---|
| yaw_rate_rmse (rad/s) | 0.005874 | 0.005844 | -0.5% |
| cte_rmse (m) | 56.81 | 54.19 | -4.6% |

## Per-platform CTE-drift reduction

| platform | V1 cte_signed | shipped cte_signed |
|---|---|---|
| FORD_F_150_LIGHTNING_MK1 | +0.32 m | -1.10 m |
| FORD_MUSTANG_MACH_E_MK1  | -21.98 m | +3.11 m |
| HYUNDAI_IONIQ_5          | -11.57 m | +1.03 m |
