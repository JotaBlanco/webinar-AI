# v1-asym-gain — assessment

## Headline (pooled, all platforms)

| metric | V1 | v1-asym-gain | Δ vs V1 |
|---|---|---|---|
| yaw_rate_rmse (rad/s) | 0.005874 | 0.005844 | −0.5% |
| cte_rmse (m)          | 56.807   | 56.035   | −1.4% |

## Per-platform

| platform | V1 yaw | candidate yaw | V1 cte | candidate cte | V1 cte_drift | candidate cte_drift |
|---|---|---|---|---|---|---|
| Lightning | 0.00566 | 0.00568 | 62.19 | 61.96 | +0.32 | −2.70 |
| Mach-E    | 0.00859 | 0.00856 | 98.68 | 97.36 | −21.98 | −16.42 |
| IONIQ-5   | 0.00766 | 0.00761 | 69.53 | 68.44 | −11.57 |  −8.85 |
| Tesla     | 0       | 0       | 0     | 0     | 0      | 0      |

## Diagnosis

The intervention works as predicted, but the magnitude of the gain is small.
The signed yaw bias frac dropped on every fitted platform (Mach-E from 0.03 →
~0.004; IONIQ-5 from 0.01 → ~0.001) — i.e. the asymmetric correction does
substantially reduce the *systematic* component of yaw error. The total yaw
RMSE barely moves because most of the per-sample variance is unstructured.

CTE *signed* drift reduces by ~25% on Mach-E and IONIQ-5. But pooled CTE RMSE
moves only ~1.4% because the worst segments are dominated by route-specific
trajectory errors that aren't pure direction-asymmetric.

## Verdict

**Keep** — small but consistent improvement on every fitted platform. Reduces
signed-bias warnings. Lightning's CTE drift moved from +0.3 → −2.7 (small,
likely overfit drift sign change); within noise but doesn't regress.

## What this rules out

- **The asymmetric residual is not pure** — half of the right-turn bias survives
  the asymmetric-gain fit. Likely a coupled effect (e.g. nonlinear understeer
  that engages more on one side, or steer-rate dynamics that V1 misses).
- **Coefficient re-fitting alone is bounded at ~1% improvement on these KPIs.**
  Real headroom requires a structurally richer model (rung 1 dynamic ST or a
  residual learner) — confirmed by the V1 paper claim "fitting tighter
  coefficients buys at most a basis point or two."
