# v1-plus-resid — notes

## Formulation

V1 yaw rate is computed exactly as in `code/v1_baseline.py`. On top of V1, a
per-platform linear correction is added:

```
yr_pred = yr_v1 + intercept + Σ_i w_i · feature_i(t)
```

with features (all allowlist-safe):

| feature | meaning |
|---|---|
| `v_mps`              | longitudinal speed |
| `delta_road_rad`     | road-wheel angle |
| `d_delta_dt`         | np.gradient(delta_road_rad, t_s) |
| `a_long_mps2`        | longitudinal accel |
| `yr_v1`              | V1's yaw rate output |
| `abs_delta`          | abs(delta_road_rad) |
| `yr_v1_sq_signed`    | sign(yr_v1) · yr_v1² |

## State-space

No new states. The model is a memoryless additive correction on V1's output.
This deliberately avoids stability issues you'd inherit from a rung-1 ODE
integrator at openpilot priors (see `references/dynamics-formulations.md`).

## Integrator

None — the V1 first-order lag still runs underneath; the residual term is
applied after it. Trajectory integration is then the standard Euler scheme
that `_shared/traj_metrics.py` uses.

## Priors / fit

- Coefficients in `coeffs.json` are fit per-platform by ridge regression
  (`lam = 1e-3 * n_rows`) on every sim/segments/<plat>/**/sim.csv row where
  `v_mps > 2.0`, subsampled at every 4th sample for speed.
- The fit is run by `out/fit_residual.py`.
- Intercept is *not* regularised.

## Expected residual character (which V1 residual this attacks)

- Mach-E and IONIQ-5 each have a signed CTE drift (−22 m, −12 m respectively)
  on top of V1. This is **platform-level yaw-bias structure** that V1 cannot
  represent with its pre-shipped coefficients.
- The intercept term of the per-platform fit picks up this bias directly;
  pooled signed yaw bias collapses to ≈0 after correction on every platform.
- The other six features pick up a small (R² ≈ 0.02–0.07) additional
  amount of regime-dependent structure — e.g. yr_v1²-signed represents a
  mild quadratic correction in yaw-rate magnitude (effective understeer
  saturation hint).

## Why this is structurally-different from V1

V1's transfer function is steady-state-kinematic + one real pole. This
candidate adds an external feedforward that is a linear combination of
allowlist features (some of which V1 doesn't read at all, e.g. `a_long_mps2`
and `dδ/dt`). It cannot be reduced to a re-fit of V1's five physical
coefficients.
