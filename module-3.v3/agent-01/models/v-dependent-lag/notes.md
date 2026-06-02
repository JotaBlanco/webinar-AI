# v-dependent-lag

## Formulation
Same as V1 except the lag time constant:
```
τ(v) = τ0 + τ1 / max(v, 1)
α[i] = dt[i] / (τ(v[i]) + dt[i])
y[i] = y[i-1] + α[i] * (y_ss[i] - y[i-1])
```

## Inputs / state
Inputs identical to V1. Internal state: lagged yaw. Per-platform (τ0, τ1) fit by grid search minimising pooled yaw RMSE on `data/sim/segments/`.

## Why this attacks V1's residual
V1's first-order lag with a scalar τ ≈ 0.06–0.07 s is one parameter trying to fit two regimes: highway (high v, lag matters less) and city (low v, lag matters more). Letting τ grow at low v should improve low-speed transient response, which is where CTE accumulates most.

## Why this is `differs-from-v1`
τ is no longer a single scalar; it varies sample-to-sample with v. V1 cannot reach this output by re-fitting g/L_eff/K_us/τ.

## Result of the fit
Only IONIQ-5 picked up a non-zero τ1 (=0.05), with a marginal improvement (0.007663 → 0.007656). Mach-E and Lightning collapsed to τ1 = 0 — equivalent to V1. **The bottleneck is not lag-scheduling; it is the surviving steady yaw bias and the transient steering-rate response**, attacked instead by the bias-corrected-v1 and steering-derivative-residual candidates.
