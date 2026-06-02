# v1-asym-gain — direction-asymmetric steering gain

## Formulation

```
delta_raw = delta_road_rad − δ₀     (δ₀ as in V1, per-segment for Mach-E/IONIQ-5)
w_left    = 0.5·(1 + tanh(delta_raw / eps))     ∈ [0,1]
g_eff     = g_left · w_left + g_right · (1 − w_left)
delta     = delta_raw · g_eff
yr_ss     = v · delta / (L_eff + K_us · v²)
yr[i+1]   = yr[i] + α[i] · (yr_ss[i+1] − yr[i])      α = dt/(τ+dt)
```

Trajectory integration deferred to the scorer (Euler over yr + v_meas).

## State-space

State: scalar `yr` (the lagged yaw rate).
Inputs: `delta_road_rad`, `v_mps`, `t_s`.
Initial condition: `yr[0] = yr_ss[0]` — same as V1.
Integrator: explicit Euler first-order lag (same as V1; trivially stable for α<1).

## Parameters (per platform)

Fit via Nelder-Mead on yaw_rmse/yaw_v1 + 0.5·cte_rmse/cte_v1 (per-platform anchor).
Other params kept at V1 values.

| platform | g_left | g_right | blend_eps | L_eff (V1) | K_us (V1) | τ (V1) |
|---|---|---|---|---|---|---|
| Lightning | 0.8515 | 0.8788 | 0.005 | 3.26 | 0.0035 | 0.060 |
| Mach-E    | 0.9056 | 0.8419 | 0.005 | 2.22 | 0.0015 | 0.069 |
| IONIQ-5   | 0.9505 | 0.9193 | 0.005 | 2.887 | 0.00289 | 0.062 |

Tesla: passthrough (no truth → cannot fit; V0 is the safe output).

## Expected residual character

V1 residual diagnosis on Mach-E and IONIQ-5 showed strong **left/right
asymmetry**:

- Mach-E: turning-left residual mean ≈ −0.00032, turning-right ≈ −0.00719.
- IONIQ-5: turning-left ≈ +0.00026, turning-right ≈ −0.00547.

A symmetric δ₀ can't fix this. The asymmetric gain attacks it directly: on a
right-hand turn (delta_raw < 0), the model uses `g_right` which is calibrated
*for that direction's gain error*; same for left.

Expectation:
- Net CTE drift reduces on Mach-E (-22 m → smaller) and IONIQ-5 (-12 m → smaller).
- Marginal yaw RMSE improvement (signed bias is small relative to the noise floor).
- Lightning gain spread is small (V1 already calibrated near-symmetric); should not regress.

## Why this is structurally different from V1

V1 has a single steering scale `g` per platform. Asymmetric gain introduces a
*sign-dependent* scaling — a new functional dependence on the steering input
sign that V1 cannot express by re-tuning its existing coeffs. It is *not* a
refit of V1.

## Known limitations

- The asymmetry might not be intrinsic to the vehicle — could be a route-distribution
  artefact (e.g. more right-than-left turns in dev set). Cross-validation needed.
- The smooth blend around delta_raw≈0 is approximate; a hard switch would be
  the limit eps→0 but introduces discontinuity at the transition.
- Doesn't address transient regime yaw RMSE (still 0.0164 rad/s pooled).
