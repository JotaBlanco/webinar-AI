# notes.md — m2-fiala-tire-st

- rung: 2
- parent: m1-linear-dynamic-st
- status: drafting

## What this differs from

- **M1 (linear dynamic single-track):** M2 swaps the linear tire force
  `F_y = -C_α α` for the Fiala piecewise-saturating curve. Inside the
  linear region (|α| < α_sl = atan(3 μ F_z / C_α)) the two are
  identical to first order in α — M2 reduces cleanly to M1 at low
  lateral demand. The difference appears at high `|a_lat|`: M1
  generates unbounded force at large α, while M2 saturates at
  `μ F_z` per axle. Two new fitted params per platform (`μ_f`, `μ_r`)
  and two derived (`F_zf`, `F_zr` from static axle load) — five fitted
  params total vs. M1's three.
- **V1 (kinematic + understeer + first-order lag):** Inherits the
  transient ODE step from M1 (so all of M1's improvements over V1
  apply — no `τ` band-aid, real phase lag, `[β, ψ̇]` state). On top
  of that, V1's pure linear `F_y` is now bounded — V1 has no notion
  of tire saturation at all; M2 captures the regime where front grip
  is the limiting factor (notably F150 at sweepers).
- **Single-tire-per-axle assumption:** M2 treats each axle as one
  effective tire with axle-total `F_z` and axle-total `C_α`.
  Per-wheel lateral load transfer (inner/outer split) is M3, not M2.

## What residual symptom this targets

High-`|a_lat|` yaw RMSE — segments where M1's linear tire overshoots
because it doesn't know about the friction limit. F150 in particular
(high CG, high mass, modest μ) was diagnosed as flat-topping in the
yaw vs. δ relationship; that's a saturation signature the linear
model structurally cannot reproduce. Mach-E mid-sweeper bias should
also tighten if the rear axle was operating near α_sl. If F150 is
*still* flat after fitting M2, the next rung is M3 (per-wheel load
transfer), not more knobs on M2.
