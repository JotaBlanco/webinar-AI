# dst_relax — dynamic single-track with tyre relaxation length

- rung: 2
- parent: dst_lin (or v1)
- expected_residual: same transient regime as dst_lin, but the dst_lin
  residual itself shows short-lag autocorrelation → tyre force buildup
  is slower than dst_lin assumes. Cohort §8 ("V1's lag-τ is mis-modelling
  a structure that's non-linear in (δ, dδ/dt, v)") implies the structure
  is the v-dependent relaxation that dst_relax explicitly models.

## What this differs from

- **v1**: V1's lag-τ is a single output-side first-order filter with v-
  independent τ. dst_relax has *two* relaxation states (per axle), driven
  by v-dependent time constants τ = σ/v. The lag here is physically
  motivated, not phenomenological.
- **dst_lin**: dst_lin assumes instantaneous tyre force (F_y = -C_α·α at
  the current α). dst_relax adds the carcass dynamics. At very high v
  (τ → 0), dst_relax → dst_lin.
- **dst_nl**: orthogonal change. dst_nl changes the *shape* of the tyre
  force curve (saturation); dst_relax changes the *timing* of force
  buildup. A future model could combine both (state-space with relaxed
  Pacejka tyres); the catalogue ships them separately so the agent can
  see which residual character each attacks.
- **dst_load**: also adds per-axle physics, but via load transfer.

## When to pick

- After dst_lin, the residual is **autocorrelated at very short lag**
  (1–3 samples) but no longer feature-correlated with d(delta_road)/dt.
  That's the signature of unmodeled tyre-relaxation dynamics.
- High-speed (>20 m/s) data where τ_relax = σ/v becomes small but
  non-negligible.

## When NOT to pick

- Data is low-speed (<8 m/s) dominated: τ = σ/v is too large; relaxation
  becomes the dominant dynamic and the LP1 model may misbehave.
- Fit diagnostics flag `stuck_on_bound:sigma_relax` (sigma pinned to the
  upper bound) → data doesn't have the excitation to identify it.

## How to refit

    cp -r physics-catalog/dst_relax models/dst_relax-fitted
    python -m physics-catalog.dst_relax.fit
    cp physics-catalog/dst_relax/coeffs.json models/dst_relax-fitted/coeffs.json
    python -m skills.iterate.iterate models/dst_relax-fitted
