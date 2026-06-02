# notes.md — m1-linear-dynamic-st

- rung: 1
- parent: v1
- status: drafting

## What this differs from

- **v1 (kinematic single-track + understeer + first-order lag + per-segment δ₀):**
  M1 replaces V1's *steady-state* lateral dynamics with a *transient* ODE.
  V1 outputs a yaw rate algebraically from `(δ, v)`; M1 evolves the
  two-state vector `[β, ψ̇]` through tire forces. The first-order time-lag
  band-aid in V1 (`τ`) is removed — the dynamic model produces phase lag
  naturally. The same per-segment δ₀ trick V1 uses is dropped here on
  purpose: M1 should explain the kinematic residual *physically*, not
  via a learned offset. Add it back if dev shows persistent per-segment
  bias.
- **Why this and not refining V1:** every cohort since m3.v2 has refined
  V1 and plateau'd. M1 climbs the dynamics ladder — the rung the cohort
  has never tested.

## What residual symptom this targets

Transient-regime yaw RMSE (V1's first-order `τ` lag cannot follow
high-`d(δ)/dt` inputs), and per-platform signed yaw bias on platforms
where the steady-state assumption breaks (notably Mach-E in mid-`a_lat`
sweepers).
