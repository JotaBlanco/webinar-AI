# final-model REPORT (stub)

Full narrative lives in the parent REPORT.md. This stub exists so preflight
can confirm bundle completeness.

## Shipped model

V1 + 8-feature linear correction (`1, |delta|*delta, v*delta, v^2*delta,
delta^3, ddelta/dt, ddelta/dt*v, sign(delta)*delta^2*v`), per-platform fit on
V1 residuals against truth.

| metric | V1 | shipped | Δ |
|---|---|---|---|
| pooled yaw RMSE (rad/s) | 0.005874 | 0.005552 | -5.5% |
| pooled CTE RMSE (m) | 56.81 | 54.56 | -4.0% |
