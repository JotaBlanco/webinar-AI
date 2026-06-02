# residual-learner — formulation

## Idea
V1 leaves a yaw residual that correlates with measurable features. Predict
the residual from features and subtract it from V1's output.

## Formulation
```
features: f = [yr_v1, |yr_v1|, v, v·yr_v1, dδ/dt, δ, 1]   (length 7)
residual: r_hat = f · w                                    (per platform)
output:   yr_hat = yr_v1 − r_hat
```

`w` per platform fit by ridge regression on (V1 − truth):
```
w = argmin || F w − r ||² + λ ||w||²
```
with λ=30 (chosen by sweep — sweet spot on dev pooled yaw RMSE before CTE
starts increasing).

## State / integrator
None. Pure point-wise post-correction.

## Inputs (all allowlist)
t_s, v_mps, delta_road_rad, yaw_rate_pred_rads — derivatives computed by
numpy.gradient.

## Why this is structurally different from V1
V1 is a fixed-shape kinematic model with 4 fitted scalars (g, K_us, τ, δ₀).
It cannot express a yaw correction that depends on v, |yr|, or dδ/dt
*independently* — those couplings are baked into the V1 shape.
The residual-learner can: e.g. it gives a non-zero correction when V1's gain
is right but its transient response is late.

## Expected residual character
- Lightning: small correction (V1 already near floor); main effect is variance
  redistribution.
- Mach-E and IONIQ-5: large CTE-drift reduction from the constant + yr_v1
  columns (handles the gain error V1 misses).
