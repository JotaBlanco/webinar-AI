# notes.md — m4-relaxation-length

- rung: orthogonal
- parent: v1
- status: drafting

## What this differs from

- **v1 (kinematic single-track + understeer + first-order *time* lag + per-segment δ₀):**
  M4 keeps V1's kinematic core unchanged — same `g`, `L_eff`, `K_us`,
  and δ₀ policy (per-segment for Mach-E / Ioniq, global for F150) — and
  ONLY swaps the lag stage. V1's fixed-`τ` first-order time lag is
  replaced by a distance-domain relaxation length `σ` (meters). At
  constant `v` this is equivalent to `τ = σ / v`, i.e. the lag shortens
  as the car goes faster, which is the physically correct behaviour V1
  gets wrong with one global `τ` per platform. The single fitted
  parameter is `σ`.
- **m1 / m2 / m3 (dynamics-ladder rungs 1–3):** M4 is *orthogonal* to
  the dynamics ladder. It does not introduce sideslip state, slip-angle
  tires, Fiala saturation, or load transfer. The hypothesis is
  cohort-independent: if V1's residual is dominated by *speed-dependent
  phase lag* (and not by missing dynamics), then the cheapest correct
  fix is to replace `τ` with `σ`, not to climb to LDST. M4 can ship
  alongside any future LDST refinement; it does not compete with the
  ladder, it composes with it.
- **Why this and not refining V1's `τ`:** every cohort that has tuned
  `τ` per platform has plateau'd at the speed it tuned for. The error
  mode is structural — a constant-`τ` filter cannot match a system whose
  characteristic time scales with `1/v`. Refit `τ` and the same residual
  shape comes back at a different speed band.

## What residual symptom this targets

Speed-dependent yaw phase error: V1's residual rises at both very low
and very high speed even after `τ` is well-tuned for the cohort-median
speed. Ramp-steer segments are the cleanest tell — V1 lags too much
when the car is fast through them and too little when it's slow.

## Failure modes to watch in the fit report

- `σ → 0` — relaxation collapses, M4 reduces to V1 with no lag. Acceptable
  null result; means the residual is dominated by something other than
  lag.
- `σ` very large (> ~2 m) — optimiser is using lag to mask a structural
  bug (probably a sign error or a δ₀ inconsistency). Bounded
  `[0.05, 2.0]` for this reason.
- CTE worsens while yaw improves — heading-integration drift from over-
  filtering. Reduce upper bound on `σ` or fall back to CTE objective.
