# steer-rate-ff — assessment

## Pooled scores

| metric | V1 | steer-rate-ff | Δ vs V1 |
|---|---|---|---|
| yaw_rate_rmse | 0.005874 | 0.005832 | −0.7% |
| cte_rmse      | 56.807   | 54.462   | −4.1% |

## Per-platform

| platform | yaw | CTE | yaw_bias | cte_drift |
|---|---|---|---|---|
| FORD_F_150_LIGHTNING_MK1 | 0.00565 | 62.21 | +0.00000 | −1.06 |
| FORD_MUSTANG_MACH_E_MK1  | 0.00847 | 92.12 | −0.00000 | −5.30 |
| HYUNDAI_IONIQ_5          | 0.00763 | 67.25 | +0.00000 | −3.14 |

## Verdict

Beats V1 but is dominated by v1-plus-resid on yaw RMSE. The fitted k_ff
gains were small (~−0.002 on the Fords, +0.0007 on the IONIQ-5), and the
*bias* term ended up doing most of the heavy lifting. The derivative shape
exists in the data but is much smaller than the bias structure.

## Verdict

**Shelve in favour of v1-plus-resid.**

## What this rules out

Adding a pure first-order zero on top of V1 is *not* the dominant
correction. The CTE-drift bias structure is bigger than the transient
zero structure. The richer 7-feature fit (v1-plus-resid) captures both.
