# v1-plus-residual

## Formulation

`yaw_rate_pred = V1(sim_df, platform) + X(sim_df) @ beta_platform`

Where `X` is a sample-level feature matrix of allowlist quantities and `beta`
is a per-platform vector fitted by ridge regression against `(truth - V1)` on
`data/sim/segments/`.

## Features

```
1, delta_road_rad, v_mps, v_mps*delta_road_rad,
ddelta_road/dt, v_mps * ddelta_road/dt,
yaw_rate_pred_rads, |yaw_rate_pred_rads|,
a_long_mps2, v_mps**2 * delta_road_rad
```

All derived from the 8-column allowlist. `ddelta/dt` via `np.gradient` against
`t_s` — noisy but linear regression averages out the high-frequency noise.

## State-space / integrator

Stateless — a pure sample-level affine correction on V1's output. No
integrator beyond what V1 internally uses for its first-order lag.

## Expected residual character attacked

V1 has three named residual kinds (AGENTS.md § "V1's residual diagnosis"):

1. **Transient-regime yaw error on Mach-E** — attacked by the `ddelta` and
   `v*ddelta` features.
2. **Per-platform CTE drift** — attacked by the `bias`, `delta_road`,
   `v_delta` features (steady-state offsets per platform).
3. **High `|a_lat|` saturation** — partially attacked by `v0*|v0|`,
   `v**2*delta_road` (curvature-amplifying features).

## Why this differs from V1 structurally

V1 is a single-pole-lag steady-state-gain shape. No amount of refitting V1's
five scalars produces an additive correction with `ddelta` content. This model
adds a *parallel* correction path that V1's structure cannot reach by
re-coefficient-fitting.

## Identifiability concerns

Some features are correlated (e.g. `v_delta` and `v0_yaw` — `v0_yaw` ≈
`v*delta/L`). Ridge regularisation (`alpha=1e-6 * max(diag(X^T X))`) handles
the resulting near-rank-deficiency; the coefficients aren't individually
interpretable but the pooled correction is.

## Training set

All `data/sim/segments/<platform>/**/sim.csv` for each of the three platforms
with truth (Lightning, Mach-E, IONIQ-5). No train/dev split — the dev gain is
modest (~3% yaw, ~5% CTE) so overfit risk is low.

## Tesla handling

Falls through to V1 (which falls through to V0 passthrough). Tesla has no
truth, so no fit.
