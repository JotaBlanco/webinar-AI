# dst_nl — Pacejka-lite nonlinear tyre dynamic single-track

- rung: 2
- parent: dst_lin (or v1 if dst_lin not in the search tree)
- expected_residual: nonlinear high-α structure — large slip angles in
  fast-curvature or braking-into-corner segments where the linear tyre
  underestimates force, then overshoots when α grows. Cohort §8 evidence
  that V1's lag-τ is mis-modelling a structure non-linear in (δ, dδ/dt, v).

## The tyre model

Pacejka simplified:

    F_y = -μ · F_z · sin(C · atan(B · α))
    B   = C_α / (C · μ · F_z)

Reproduces the linear stiffness at small α (B chosen so the slope matches
C_α) and saturates at -μ·F_z·sin(C·π/2) ≈ -μ·F_z. Five fitted params per
platform: {C_αf, C_αr, I_z, μ, C}.

## What this differs from

- **dst_lin**: identical state-space (β, ψ̇), identical wheelbase / mass
  geometry. The only difference is the tyre-force function. dst_nl
  collapses to dst_lin at small α. If `assess-candidate-model` reports
  the residual is dominated by `|α| > 0.05 rad` samples, dst_nl is the
  correct climb; if not, you're paying for a parameter (μ) you don't need.
- **v1**: V1 has no slip angles at all — it computes yaw rate from
  steering geometry. dst_nl is two structural rungs above V1.
- **dst_load**: dst_load also has saturation-ish behaviour (per-axle F_z
  changes under braking), but via load transfer rather than tyre
  nonlinearity. dst_load applies when the saturation is *induced* by
  longitudinal forces; dst_nl applies when it's inherent.

## When to pick

- Residual after dst_lin shows positive residual on outside-front-tyre
  during peak cornering → tyre is saturating; linear model overshoots.
- High σ across folds on Lightning specifically (heavy vehicle → more
  vertical load transfer → tyres in more nonlinear regimes more often).

## When NOT to pick

- |α| stays < 0.04 rad across the whole dev pool (highway-only data).
  dst_nl == dst_lin in that regime, and you're paying for extra params.
- Fit diagnostics flag `stuck_on_bound:mu` (mu pinned to 1.3 upper bound)
  → either data lacks saturation regimes, or initial guesses are wrong.

## How to refit

    cp -r physics-catalog/dst_nl models/dst_nl-fitted
    python -m physics-catalog.dst_nl.fit
    cp physics-catalog/dst_nl/coeffs.json models/dst_nl-fitted/coeffs.json
    python -m skills.iterate.iterate models/dst_nl-fitted
