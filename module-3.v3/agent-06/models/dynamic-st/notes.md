# dynamic-st — formulation (rung-1 linear dynamic single-track)

## Equations
```
α_f = δ − (vy + l_f · yr) / vx
α_r = −(vy − l_r · yr) / vx
F_yf = C_αf · α_f
F_yr = C_αr · α_r
vy_dot = (F_yf + F_yr) / m − vx · yr
yr_dot = (l_f · F_yf − l_r · F_yr) / Iz
```

## State
States: (vy, yr). Initial vy=0; initial yr from V0 baseline.

## Inputs
- δ = (delta_road_rad − δ₀) · g  — V1's per-segment δ₀ correction kept in front.
- vx = max(v_mps, 1.0) — clamped to avoid singularity.

## Integrator
RK4 with sub-stepping at 2.5 ms inside each 20 ms tick. Explicit RK4 at the
native 20 ms rate explodes at openpilot C_α priors — confirmed empirically.
Also clamps |vy| < 50 m/s and |yr| < 2 rad/s as a safety net.

## Coeffs
Per platform: m, Iz, l_f, l_r, C_αf, C_αr from openpilot carParams. V1's `g` kept.
Per-platform affine post-fit (a, b) applied to the output to absorb gain mismatch.

## Expected residual character
Should improve transient-regime yaw (V1's first-order lag is replaced by the
true dynamics). Risk: K_us_dyn ≈ 0.0017 is lower than V1's *fitted* K_us
(0.0015–0.0035) — predicts a *higher* steady-state yaw for the same δ than V1.
