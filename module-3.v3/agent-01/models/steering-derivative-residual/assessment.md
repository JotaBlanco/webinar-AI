# Assessment — steering-derivative-residual

## Pooled dev scores
- yaw_rate_rmse: **0.005827 rad/s** (V1: 0.005874 → −0.8%)
- cte_rmse:      **54.509 m** (V1: 56.807 → −4.0%)

## Per-platform
| platform | yaw RMSE | CTE RMSE | yaw bias | CTE drift |
|---|---|---|---|---|
| Lightning | 0.00565 | 62.23 | +0.00017 | +0.92 |
| Mach-E    | 0.00847 | 92.37 | −0.00009 | −6.36 |
| IONIQ-5   | 0.00762 | 67.24 | +0.000005 | −3.07 |

## Residual diagnosis
The linear residual learner soaks up the steady bias (constant term `d`) on Mach-E and IONIQ-5 — yaw mean residuals collapse to near zero. Marginal additional gain on yaw RMSE (transient regime improves slightly) over a pure bias correction, but CTE is fractionally worse because the steering-rate features inject some noise that bias-only doesn't.

## Verdict
**Shelve in favour of bias-corrected-v1.** Slightly better pooled yaw, slightly worse pooled CTE. Net wash; complexity surface larger (12 coefficients vs 2). The cleaner candidate ships.

This is a useful negative result: most of V1's CTE residual is captured by a single per-platform constant, not by a steering-rate-correlated model. The transient regime is small enough in sample-weighted RMSE terms that a richer model doesn't earn its complexity.
