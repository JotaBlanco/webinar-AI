# dynamic-single-track (rung-1)

## Formulation (planned)

Linear bicycle model. States `(v_y, ψ̇)` with measured `(v_x, δ)`:

```
β = v_y / v_x
α_f = δ - β - a · ψ̇ / v_x          # front slip
α_r = -β + b · ψ̇ / v_x             # rear slip
F_yf = C_f · α_f                    # linear tyre
F_yr = C_r · α_r
m · (v̇_y + v_x · ψ̇) = F_yf · cos δ + F_yr
I_z · ψ̈                = a · F_yf · cos δ - b · F_yr
```

Five identifiable parameters per platform: `(m, I_z, a, b, C_f, C_r)`.
`m` and `I_z` are platform-known (carParams). Identifiability constraint on
`(a, b)`: `a + b = L_eff_v1`. Free parameters per platform: `(a/L, C_f, C_r)`.

Integrator: implicit Euler at sim_df's native sample rate (50 Hz). Initial
state from straight-row average (ψ̇₀ = 0, β₀ = 0).

## State-space

| symbol | meaning | initial |
|--------|---------|---------|
| v_y    | lateral velocity (m/s) | 0 |
| ψ̇      | yaw rate (rad/s) | 0 |

Inputs: `v_x = v_mps`, `δ = delta_road_rad`.

## Expected residual character attacked

The transient yaw error on Mach-E (the worst-fitted platform) is what a
dynamic model is best suited for: V1's first-order lag is a single-pole
approximation of the cornering-stiffness dynamics that this model has by
construction.

## Status

**Not implemented in this run** (time budget). The fitting effort for
`(a/L, C_f, C_r)` per platform is multi-iteration nonlinear and competes
with the much cheaper residual-learner gain. Listed for the registry and so
the cohort can see the alternative was considered.
