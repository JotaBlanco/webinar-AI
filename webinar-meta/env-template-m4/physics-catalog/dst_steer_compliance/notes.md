# dst_steer_compliance — steering compliance + Ackermann split

- rung: 2
- parent: dst_lin
- expected_residual: residual that scales with delta_road_rad × F_yf, i.e.
  more error at large steering + high cornering load. Cohort §8: V1's lag-τ
  is mis-modelling a structure non-linear in (δ, dδ/dt, v). This model
  tests whether that structure is *steering compliance* (the road-wheel
  angle is less than the commanded angle under load) rather than tyre dynamics.

## The physics

Two effects on top of dst_lin:

1. Compliance — the road-wheel angle the tyre sees is reduced by the
   lateral force:
       δ_effective = δ_commanded − K_compl · F_yf
   K_compl ∈ ~1e-7 to 1e-4 rad/N. Implemented as a 2-iteration
   fixed-point inside each RK4 derivative evaluation (cheap; ~6 extra
   ops per step).

2. Ackermann — geometric inner/outer wheel split modelled as a small
   angle correction proportional to |δ|:
       δ_effective_axle = δ · (1 − k_ack · |δ|)
   k_ack ∈ [-0.5, 0.5]. 0 = ideal single-track. Positive = parallel
   steering (inner under-steered), negative = true Ackermann.

State: [β, ψ̇]. Fitted: {C_αf, C_αr, I_z, K_compl, k_ackermann}.

## What this differs from

- **dst_lin**: dst_lin assumes δ_road_rad in the input *is* the angle
  the tyre sees. dst_steer_compliance allows the actual tyre angle to
  differ.
- **dst_nl**: dst_nl's nonlinearity lives in the tyre force curve at the
  same α. dst_steer_compliance's nonlinearity lives in the α itself
  (because effective δ depends on F_yf which depends on α). They could
  compose, but ship separately so we can attribute.
- **dst_relax**: dst_relax adds a time-domain lag from carcass dynamics.
  dst_steer_compliance has no time dependence — it's an instantaneous
  fixed-point. If V1's lag-τ is mis-modelling *steady-state* compliance
  rather than *transient* relaxation, this model captures it; dst_relax
  doesn't.

## When to pick

- Residual after dst_lin scales with |δ| (not d(δ)/dt) — points at a
  *steady-state* nonlinearity, not a transient.
- Heavy vehicles or stiff tyres where K_compl is meaningfully large
  (Lightning prior is 1.5e-5 vs 1.0e-5 for sedans).

## When NOT to pick

- Fitter pegs K_compl to its lower bound (1e-7) → data lacks lateral-load
  variation to identify it.
- Data has uniform steering amplitude (no |δ| variation) → k_ackermann
  unidentifiable.

## How to refit

    cp -r physics-catalog/dst_steer_compliance models/dst_steer_compliance-fitted
    python -m physics-catalog.dst_steer_compliance.fit
    cp physics-catalog/dst_steer_compliance/coeffs.json models/dst_steer_compliance-fitted/coeffs.json
    python -m skills.iterate.iterate models/dst_steer_compliance-fitted
