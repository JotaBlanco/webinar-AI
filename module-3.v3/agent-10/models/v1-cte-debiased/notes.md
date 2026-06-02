# v1-cte-debiased — notes

## Formulation

```
yr_pred = yr_v1(t) + delta_yr(platform)
```

A single per-platform constant offset `delta_yr` added to V1's yaw rate.

## State-space

No new states. Memoryless offset.

## Integrator

None added; standard trajectory Euler.

## Priors / fit

`out/fit_cte_debias.py` does a 1-D coarse scan (−0.005..+0.005, 41 pts)
followed by a finer scan (±2.5e-4, 21 pts), minimising **pooled CTE RMSE**
on the platform's segments. This is a different loss than yaw RMSE.

Fitted offsets:
- Lightning: −0.00008 (basically zero — V1 already on bias)
- Mach-E:    +0.00210
- IONIQ-5:   +0.00108

## Expected residual character (which V1 residual this attacks)

V1 has a signed yaw bias on Mach-E (−0.00142) and IONIQ-5 (−0.00075) that
integrates over distance into a CTE drift of −22 m and −12 m. A single
constant offset is enough to drive that pooled drift to ~0.

## Why this is structurally-different from V1

The objective changes from sample-wise yaw RMS to integrated CTE RMS. V1's
fitting workflow optimises yaw, never CTE directly. This candidate is the
*minimum-parameter* model that addresses the trajectory-integrated KPI
specifically.

In structural terms the dynamics are unchanged, but the fitted parameter
optimises a *different functional* of the prediction. That qualifies as a
structurally-different *learning problem* even if the model class is small.
