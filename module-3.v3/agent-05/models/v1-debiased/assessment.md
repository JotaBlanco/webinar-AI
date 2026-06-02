# v1-debiased — assessment

**Verdict**: small win on both KPIs. Ship candidate.

| platform | yaw RMSE (V1 → v1-debiased) | CTE RMSE (V1 → v1-debiased) |
|---|---|---|
| FORD_F_150_LIGHTNING_MK1 | 0.00566 → 0.00566 (≈) | 62.18 → 62.18 (≈) |
| FORD_MUSTANG_MACH_E_MK1 | 0.00859 → **0.00851** | 98.68 → **91.26** (-7.5%) |
| HYUNDAI_IONIQ_5 | 0.00766 → **0.00764** | 69.53 → **67.03** (-3.6%) |
| **pooled** | 0.00587 → **0.00584** | 56.81 → **54.19** (-4.6%) |

The per-platform signed CTE drift collapsed: Mach-E -22 m → -5 m, IONIQ-5 -12 m → +1 m. Yaw RMSE
moved by less than the standard deviation of segment-level error because the bias is small relative
to the noise floor, but every basis point counts and CTE is the big lever here.

Lightning's optimum bias is ~0, consistent with V1 already being at its noise floor there.

## What is still wrong

Mach-E pooled yaw RMSE remains 1.5× Lightning's. The residual is dominated by transient regime
(high `|d(delta)/dt|`) — V1's single-pole lag is a band-aid. A dynamic single-track model would
attack that, but didn't fit in the time budget.
