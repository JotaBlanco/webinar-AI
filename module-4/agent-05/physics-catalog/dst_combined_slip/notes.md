# dst_combined_slip — friction-circle longitudinal × lateral coupling

- rung: 2
- parent: dst_lin
- expected_residual: brake-into-corner segments where the linear tyre
  over-predicts F_y because the tyre is simultaneously generating F_x
  for braking. Cohort §2 + §9: Lightning's residual is concentrated in
  exactly these segments.

## The physics

Friction-circle / ellipse constraint per axle:

    F_x² + F_y² ≤ (μ · F_z)²

With F_x consumed by longitudinal force, available F_y is reduced. Per
axle:

    F_x_total = m · a_long
    F_x_f = α_drive · F_x_total
    F_x_r = (1 - α_drive) · F_x_total
    F_y_max_axle = sqrt(max((μ·F_z_axle)² - F_x_axle², 0))
    F_y(α)       = clamp(-C_α · α, ±F_y_max)

State: [β, ψ̇]. Fitted (per platform): {C_αf, C_αr, I_z, μ, α_drive}.
α_drive is the front-axle share of longitudinal force; encodes whether
the vehicle is rear-drive, front-drive, or AWD-biased.

## What this differs from

- **dst_lin**: dst_lin assumes infinite F_y headroom. dst_combined_slip
  is dst_lin where the tyre saturates from *combined* loading. Collapses
  to dst_lin when |a_long| ≈ 0.
- **dst_nl**: dst_nl saturates from large α (Pacejka curve). dst_combined_slip
  saturates from large F_x at small α. They're *physically distinct
  mechanisms* for the same observable (reduced cornering force in
  high-stress regimes).
- **dst_load**: dst_load changes the *effective F_z* and rescales C_α;
  the linear F_y(α) law still holds. dst_combined_slip leaves F_z static
  but clips F_y at the friction-circle. Cohort §8 suggests the V1 lag-τ
  is mis-modelling a non-linear structure; load-transfer (dst_load) and
  combined-slip (this) are two physically-grounded candidates for what
  that structure is.

## When to pick

- Segments with significant |a_long| AND simultaneous steering (the
  classic brake-into-corner / accel-out-of-corner setpiece).
- A residual that scales with `a_long_mps2 · delta_road_rad` (the
  diagnostic feature for combined-slip).
- Lightning specifically — RWD-biased α_drive ≈ 0.3 (default) means
  rear-axle F_x dominates during braking, and the rear tyre is what
  determines yaw stiffness.

## When NOT to pick

- Highway cruising data: a_long ≈ 0, friction-circle never bites.
- Fit pegs α_drive to a bound → data lacks the F_x variation to
  identify the drive distribution.

## How to refit

    cp -r physics-catalog/dst_combined_slip models/dst_combined_slip-fitted
    python -m physics-catalog.dst_combined_slip.fit
    cp physics-catalog/dst_combined_slip/coeffs.json models/dst_combined_slip-fitted/coeffs.json
    python -m skills.iterate.iterate models/dst_combined_slip-fitted
