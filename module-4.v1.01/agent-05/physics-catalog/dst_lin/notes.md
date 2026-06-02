# dst_lin — linear dynamic single-track

- rung: 1
- parent: v1
- expected_residual: transient-dynamics-shaped (autocorr at short lag,
  correlates with d(delta_road)/dt and v_mps); V1's lag-τ band-aid lives
  in the same residual.

## What this model is

Two-state (β, ψ̇) ODE with linear small-angle tyres:

    F_yf = -C_αf · α_f
    F_yr = -C_αr · α_r
    α_f  = β + (l_f · ψ̇) / v - δ
    α_r  = β - (l_r · ψ̇) / v

Integrated via RK4. Falls through to V0 passthrough below 2 m/s (state is
ill-conditioned there).

Fitted parameters per platform: **{C_αf, C_αr, I_z}**. Cohort §1 + §7
verdict: every rung-1 attempt that used carParams values for these failed
catastrophically; fitting them is the difference.

## What this differs from

- **v1** (kinematic single-track + understeer + 1st-order lag): V1 has no
  state, no slip angles, no inertia. V1's "lag-τ" is a phenomenological
  output-side filter; dst_lin's lag is *physical* (yaw inertia × tire
  stiffness). If V1's lag-τ is mis-modelling a structural pattern (cohort
  §8), dst_lin should land where V1 can't.
- **rung-0 per-platform bias correction**: bias trims V1's systematic
  offset; dst_lin attacks the transient regime instead. Stackable — a
  rung-0 bias on top of dst_lin is reasonable if the residual after
  dst_lin still shows a signed bias.
- **dst_nl**: dst_nl uses a saturating Pacejka-lite tyre instead of
  F_y = -C_α·α. dst_lin is the small-angle limit of dst_nl. Pick dst_lin
  when the data lives in |α| < 0.1 rad (steady cornering on highway);
  pick dst_nl when high-curvature / braking segments dominate the
  residual.
- **dst_regime**: regime-switched dst_lin (V1 below threshold, dst_lin
  above). dst_lin is the unconditional version — appropriate when the
  whole speed range needs the dynamic correction. dst_regime is the move
  when the cohort §1 worry ("dynamic ST hurts at low speed") is real.
- **dst_relax**: dst_relax adds a tyre-relaxation lag inside the model.
  dst_lin assumes instantaneous tyre force build-up; dst_relax says
  no, there's a v-dependent first-order lag from the tyre carcass.

## When to pick this model

- Residual character at noise floor on bias / understeer levers, but
  autocorrelated at short lag → dst_lin is the first climb to try.
- High σ across folds at the current rung-0 fit → suggests the fit is
  fighting a transient, which dst_lin captures structurally.

## When NOT to pick this model

- If `residual-structure` says `noise_floor` AND `vs_v1` is already at the
  V1 ceiling → try the residual learner (cohort §4) instead.
- If the data has poor excitation (long highway cruising) → C_αf and C_αr
  collapse to a ratio rather than separate values. The fitter will flag
  `stuck_on_bound`; route to `drop_lever_unidentifiable`.

## How to refit

    cp -r physics-catalog/dst_lin models/dst_lin-fitted
    python -m physics-catalog.dst_lin.fit
    cp physics-catalog/dst_lin/coeffs.json models/dst_lin-fitted/coeffs.json
    python -m skills.iterate.iterate models/dst_lin-fitted

`fit.py` writes `route_cv_sigma_yaw` and `route_cv_sigma_cte` into
`coeffs.json` under each platform, so the bias_without_route_cv gate is
satisfied automatically.
