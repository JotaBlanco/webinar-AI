# MODELS.md — registry of candidate models

V1's pooled-dev scores for comparison: `yaw_rmse = 0.005874 rad/s`, `cte_rmse = 56.81 m`.

---

## affine-v1
- dir: models/affine-v1/
- structure: refines-v1
- status: assessed
- pooled-yaw-rmse-dev: 0.005859
- pooled-cte-rmse-dev: 54.98
- verdict: small but real win (-3.2% CTE, -0.3% yaw). Pure per-platform (a, b)
  affine post-correction on V1's yr. Subsumed by residual-learner (which
  contains the same two columns plus richer features). Keep as benchmark.

## dynamic-st
- dir: models/dynamic-st/
- structure: differs-from-v1
- status: assessed
- pooled-yaw-rmse-dev: 0.006549
- pooled-cte-rmse-dev: 58.98
- verdict: LOSS. Linear dynamic single-track ODE on (vy, yr), RK4 at 2.5 ms
  sub-step (full-step was unstable at openpilot C_α priors — confirms the
  references' warning), V1 δ₀ kept in front, per-platform affine post-fit
  on the output to absorb gain mismatch. Even after the affine layer it
  loses to V1 by +11% yaw / +4% CTE — the rung-1 formulation does not, by
  itself, beat the rung-0 ceiling because V1's K_us was tuned on data and
  the rung-1 K_us_dyn (derived from carParams Iz / C_α) is lower. With the
  budget, refitting C_α would push it further — left for next iteration.

## residual-learner  *(shipped)*
- dir: models/residual-learner/
- structure: differs-from-v1
- status: shipped
- pooled-yaw-rmse-dev: 0.005770
- pooled-cte-rmse-dev: 53.78
- verdict: WIN on both KPIs (-1.8% yaw, -5.3% CTE vs V1). Per-platform ridge
  regression (λ=30) of V1's yaw residual on 7 allowlist features
  [yr_v1, |yr_v1|, v, v*yr_v1, ddelta/dt, delta, 1]. Composes with V1 by
  subtracting the predicted residual. Tesla → V0 passthrough. CTE drift
  collapses from -22 m → -8.9 m on Mach-E and -11.6 m → +1.9 m on IONIQ-5.
