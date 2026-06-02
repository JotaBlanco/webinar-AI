# v1-cte-debiased — assessment

## Pooled scores

| metric | V1 | v1-cte-debiased | Δ vs V1 |
|---|---|---|---|
| yaw_rate_rmse | 0.005874 | 0.005843 | −0.5% |
| cte_rmse      | 56.807   | 54.188   | −4.6% |

## Per-platform

| platform | yaw | CTE | yaw_bias | cte_drift |
|---|---|---|---|---|
| FORD_F_150_LIGHTNING_MK1 | 0.00566 | 62.17 | +0.00004 | −0.57 |
| FORD_MUSTANG_MACH_E_MK1  | 0.00850 | 91.26 | +0.00068 | +2.76 |
| HYUNDAI_IONIQ_5          | 0.00763 | 67.03 | +0.00033 | +0.53 |

## Verdict

Beats V1 on CTE alone (best of the three candidates on CTE: 54.19 vs 54.30
for v1-plus-resid). Loses on yaw RMSE (0.00584 vs 0.00573 for v1-plus-resid).

The numbers prove that V1's pooled CTE excess can be **almost entirely**
collapsed by a single per-platform constant. The remaining CTE-RMSE pool
(54 m) is genuine per-segment shape error, not platform-level drift.

## Verdict

**Shelve in favour of v1-plus-resid** — both KPIs matter, and v1-plus-resid
wins jointly. Keep this script around as a diagnostic: the fitted offsets
are an upper bound on what a yaw-bias correction can buy on each platform.

## What this rules out

The remaining CTE-RMSE pool after bias-correction is genuinely
segment-shape variance, not a global mis-calibration. Going after it requires
either (a) per-segment correction (route bias), or (b) a structurally
better dynamics model (rung 1+).
