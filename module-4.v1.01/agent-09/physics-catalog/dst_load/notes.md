# dst_load — longitudinal-load-transfer single-track

- rung: 3 (coupled long/lat dynamics)
- parent: dst_lin (or v1)
- expected_residual: brake-into-corner and accel-out-of-corner segments
  where the linear single-track underpredicts yaw response because actual
  axle loads differ from the static F_z assumption. Cohort §2 data hints
  the Lightning residual is concentrated in these segments — high CG +
  heavy truck = the largest dynamic load transfer per unit a_long.

## The physics

Static axle loads (no a_long):
    F_z_f_static = m·g·l_r / L
    F_z_r_static = m·g·l_f / L

Load transfer under longitudinal accel:
    ΔF_z = m · a_long · h_cg / L       (positive a_long → rearward shift)
    F_z_f(t) = F_z_f_static - ΔF_z
    F_z_r(t) = F_z_r_static + ΔF_z

Cornering stiffness scales linearly with F_z:
    C_α_f(t) = C_α_f0 · F_z_f(t) / F_z_f_static
    C_α_r(t) = C_α_r0 · F_z_r(t) / F_z_r_static

Then dst_lin's two-state ODE runs with the time-varying C_α.

Fitted (per platform): {C_α_f0, C_α_r0, I_z, h_cg}. h_cg is the load-transfer
sensitivity per unit a_long. Lightning's prior is 0.85 m (high CG truck);
Mach-E / IONIQ-5 are at 0.55 m.

## What this differs from

- **dst_lin**: dst_lin assumes static axle loads. dst_load is dst_lin where
  the axle loads are dynamic. At a_long ≈ 0, dst_load → dst_lin.
- **dst_nl**: dst_nl gets saturation from large slip angles (lateral).
  dst_load gets *effective* saturation-like behaviour from changing C_α
  (longitudinal-induced). They can compound — a future model could combine
  both (Pacejka tyres with dynamic F_z); the catalogue ships them separately
  so we can attribute gains.
- **v1**: V1 has no coupling between longitudinal and lateral dynamics at
  all. dst_load is the first model in the catalogue where a_long_mps2 is
  *load-bearing* (no pun intended).

## When to pick

- Lightning specifically — the m4.v1 cohort showed Lightning at +21% yaw
  vs +55% for the other two platforms. h_cg=0.85 m means load transfer is
  the residual character most likely to be uncaptured.
- Segments with significant |a_long| (>2 m/s²) AND simultaneous lateral
  steering. Brake-into-corner is the canonical case.

## When NOT to pick

- Highway cruising data with near-zero a_long throughout. dst_load
  collapses to dst_lin and you pay for the h_cg parameter.
- The fitter's h_cg pins to the lower bound (0.30 m) → either data is
  load-transfer-poor or the prior was too high.

## How to refit

    cp -r physics-catalog/dst_load models/dst_load-fitted
    python -m physics-catalog.dst_load.fit
    cp physics-catalog/dst_load/coeffs.json models/dst_load-fitted/coeffs.json
    python -m skills.iterate.iterate models/dst_load-fitted
