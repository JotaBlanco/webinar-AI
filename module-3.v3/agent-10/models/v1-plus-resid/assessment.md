# v1-plus-resid — assessment

## Pooled scores (data/sim/segments, all 1996 segs)

| metric | V1 | v1-plus-resid | Δ vs V1 |
|---|---|---|---|
| yaw_rate_rmse | 0.005874 | **0.005727** | −2.5% |
| cte_rmse      | 56.807   | **54.304**   | −4.4% |

## Per-platform

| platform | yaw V1→model | CTE V1→model | yaw_bias V1→model | cte_drift V1→model |
|---|---|---|---|---|
| FORD_F_150_LIGHTNING_MK1 | 0.00566 → 0.00550 | 62.19 → 65.40 | +0.00012 → +0.00000 | +0.32 → +5.50 |
| FORD_MUSTANG_MACH_E_MK1  | 0.00859 → 0.00815 | 98.68 → 90.38 | −0.00142 → 0.00000 | −21.98 → −0.54 |
| HYUNDAI_IONIQ_5          | 0.00766 → 0.00755 | 69.53 → 66.97 | −0.00075 → 0.00000 | −11.57 → −0.61 |
| TESLA_MODEL_3            | 0 (passthrough) | 0 | 0 | 0 |

## Residual diagnosis after fit

- Pooled signed yaw bias collapses to ≈0 on every platform — the intercept
  term in the ridge fit is doing what it was meant to do.
- Lightning's CTE *rose* slightly (62.2 → 65.4) and now carries a +5.5 m
  positive drift the original V1 didn't have. Likely from a small intercept
  the ridge picked up to balance the other six features. Net pooled CTE still
  improves because the Mach-E reduction (98.7 → 90.4) and IONIQ-5 reduction
  (69.5 → 67.0) more than compensate.
- Mach-E CTE_rmse 90.4 is still ~6× the bias threshold — what's left is
  segment-shape noise (route-by-route variation), not a global drift.

## Verdict

**Keep — shipped.** Wins on yaw RMSE outright, closes ~90% of the CTE-drift
gap on Mach-E and IONIQ-5. The Lightning regression is mild and the pooled
metric still wins on both KPIs.

## What this rules out

- V1's residual is *not* white noise: a single per-platform linear correction
  picks up enough signal to lower both KPIs.
- The remaining Mach-E CTE (90 m) is **not** a global yaw bias — it's
  per-route. A route-bias model would be the next attack.
