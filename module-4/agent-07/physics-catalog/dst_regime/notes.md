# dst_regime — speed-regime switched bicycle/dynamic

- rung: 1 (gated)
- parent: v1
- expected_residual: rung-1 helps in the transient regime but hurts in
  low-speed kinematic-dominated segments; gating selects the right model
  per sample. Closes the cohort §1 worry that rung-1 attempts have always
  hurt average pooled RMSE because the low-speed regime drags them down.

## The model

Two predictors blended by a smooth gate on |v · ψ̇_v0|:

    g(x) = σ((x - θ) / w)                # logistic
    yaw  = g · dst_lin(...)  +  (1-g) · v1_kin(...)

Below the speed floor (2 m/s) the output falls all the way through to V0
passthrough. Fitted: {C_αf, C_αr, Iz, θ, w} per platform.

## What this differs from

- **dst_lin**: unconditional. dst_regime is dst_lin where it's earned,
  V1-kinematic elsewhere. If the data is highway-only (high |v·ψ̇| almost
  always), dst_regime collapses to dst_lin and the gate parameters are
  redundant.
- **v1**: V1 has no rung-1 component. dst_regime hands off to dst_lin
  exactly where V1's lag-τ band-aid lives.
- **dst_nl, dst_relax, dst_load**: all unconditional. dst_regime is the
  meta-strategy of "use rung-1 where it earns its place" — orthogonal to
  which tyre model you use above the gate. A future variant could blend
  V1-below + dst_nl-above; the smooth-blend machinery transfers.

## When to pick

- Cohort §1 warning ("every rung-1 attempt has hurt") is your main concern.
- The dataset has long low-speed segments (parking lots, intersections).
- You want to A/B "dst_lin everywhere" vs "dst_lin only above θ" — fit
  dst_regime, then read out θ; if θ drops to the lower bound and gate
  saturates to dst_lin everywhere, you've learned dst_lin is preferred.

## When NOT to pick

- All your dev segments are high-speed: regime gating is dead weight.
- You've already established dst_lin is wrong even at high speed (move to
  dst_nl or dst_relax).

## How to refit

    cp -r physics-catalog/dst_regime models/dst_regime-fitted
    python -m physics-catalog.dst_regime.fit
    cp physics-catalog/dst_regime/coeffs.json models/dst_regime-fitted/coeffs.json
    python -m skills.iterate.iterate models/dst_regime-fitted
