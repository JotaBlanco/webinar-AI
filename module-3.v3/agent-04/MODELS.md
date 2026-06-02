# MODELS.md — registry of candidate models

V1 floor: `yaw_rmse = 0.005874 rad/s`, `cte_rmse = 56.81 m`.

## v1_passthrough
- dir: models/v1_passthrough/
- structure: refines-v1
- status: assessed
- pooled-yaw-rmse-dev: 0.005874
- pooled-cte-rmse-dev: 56.81
- verdict: reference floor — V1 registered explicitly as a candidate for structural comparison.

## v1_plus_nonlin
- dir: models/v1_plus_nonlin/
- structure: differs-from-v1
- status: assessed
- pooled-yaw-rmse-dev: 0.005600
- pooled-cte-rmse-dev: 54.37
- verdict: V1 + 4-feature (1, |delta|*delta, v*delta, v^2*delta) ridge correction; collapses Mach-E CTE drift from -22m to -5.8m. Beats V1 on both KPIs.

## v1_plus_rich
- dir: models/v1_plus_rich/
- structure: differs-from-v1
- status: shipped
- pooled-yaw-rmse-dev: 0.005552
- pooled-cte-rmse-dev: 54.56
- verdict: SHIPPED. Extends v1_plus_nonlin with delta^3, ddelta/dt, ddelta/dt*v, sign(delta)*delta^2*v. Best pooled yaw of the three candidates; CTE within 0.2m of v1_plus_nonlin. Attacks tyre saturation + transient regime.
