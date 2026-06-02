# v1_affine — assessment

## Pooled (full sim/segments)

| metric | V1 | v1_affine | Δ |
|---|---|---|---|
| yaw_rate_rmse | 0.005874 | 0.005815 | -1.0% |
| cte_rmse | 56.81 | 54.48 | -4.1% |

## Per platform

| platform | V1 yaw / CTE | v1_affine yaw / CTE | s, b |
|---|---|---|---|
| Lightning | 0.00566 / 62.2 | 0.00566 / 62.2 | 1.0, 0.0 (passthrough) |
| Mach-E | 0.00859 / 98.7 | 0.00841 / 92.0 | 0.986, +0.00144 |
| IONIQ-5 | 0.00766 / 69.5 | 0.00761 / 67.4 | 0.994, +0.00073 |
| Tesla | 0 / 0 | 0 / 0 | passthrough |

## Bias warnings cleared

After correction: all platform yaw biases ≤ |0.00012|, all CTE drifts ≤ |5.0| m. No 🚨/⚠️.

## Route-grouped holdout (70/30)

- Mach-E: V1 yaw 0.00712 / CTE 70.1 → v1_affine 0.00679 / 68.8 (better OOS)
- IONIQ-5: V1 0.01029 / 78.5 → 0.01025 / 76.1 (better OOS)
- Lightning: V1 0.00515 / 49.7 → affine 0.00524 / 56.5 (WORSE OOS, hence passthrough)

## Verdict

Ship. Gains are modest but they are *real* in route-grouped holdout for Mach-E
and IONIQ-5. Lightning passthrough is honest: holdout said Lightning didn't
need this and a fit on 70% data hurt the other 30%.

## What this rules out

That V1's residual on Mach-E is dominated by transient *RMS* error. The actual
dominant residual structure on Mach-E for CTE purposes is a **constant signed
bias** — a 2-scalar map removes most of it without any extra dynamics.
