# dst_twin_track — 4-wheel twin-track model with lateral load transfer

- rung: 2
- parent: dst_lin
- expected_residual: corner-segments where lateral load transfer matters
  (high-CG vehicles in fast curvature). Trucks especially — inner wheels
  unload, outer wheels gain F_z, per-axle effective C_α changes during
  the corner.

## The physics

Same β/ψ̇ state-space as dst_lin, but each axle is split into L/R wheels.
Steady-state lateral load transfer per axle:

    ΔF_z_axle = k_LLT_axle · m · a_lat · h_cg / track_width

where a_lat ≈ v·ψ̇. Per-wheel F_z then sets per-wheel cornering stiffness
(linear-load approximation): C_α_wheel = C_α_axle/2 · (F_z_wheel / F_z_static).

Fitted (per platform): {C_αf, C_αr, I_z, h_cg, track_width, k_LLT_f}.
k_LLT_r = 1 - k_LLT_f. The fitter can infer roll-stiffness distribution.

## What this differs from

- **dst_lin**: dst_lin lumps both wheels per axle. dst_twin_track splits
  them and lets lateral load transfer modulate per-axle stiffness. If the
  data has no fast cornering (a_lat small everywhere), dst_twin_track
  collapses to dst_lin and the new parameters (h_cg, track, k_LLT) are
  redundant.
- **dst_load**: dst_load is *longitudinal* load transfer (a_long → axle
  shift); dst_twin_track is *lateral* load transfer (a_lat → wheel
  shift). The two compose physically — a future model could combine
  them. Cohort §2 + §9: Lightning showed the biggest residual on
  brake-into-corner segments where BOTH transfers happen simultaneously.
- **dst_nl**: tyre saturation by α magnitude. dst_twin_track lets some
  tyres approach saturation via F_z reduction rather than α increase —
  but still uses a linear F_y(α). dst_twin_track + dst_nl tyres would be
  the natural next composition; ship one at a time so we can attribute.

## When to pick

- Lightning specifically — high h_cg (0.85) × narrow-ish track (1.85) =
  large per-axle ΔF_z in any sustained corner. m4.v1 cohort had Lightning
  at +21% vs +55% for the others; lateral load transfer is the
  cohort-untested mechanism.
- Cornering-dominated data (highway off-ramps, race tracks).

## When NOT to pick

- Low-curvature data (highway cruising) — a_lat too small, model collapses.
- Inner-wheel F_z falls below the 100 N safety floor → model degenerates.
  Check fit-diagnostics for stuck_on_bound on k_LLT_f.

## How to refit

    cp -r physics-catalog/dst_twin_track models/dst_twin_track-fitted
    python -m physics-catalog.dst_twin_track.fit
    cp physics-catalog/dst_twin_track/coeffs.json models/dst_twin_track-fitted/coeffs.json
    python -m skills.iterate.iterate models/dst_twin_track-fitted
