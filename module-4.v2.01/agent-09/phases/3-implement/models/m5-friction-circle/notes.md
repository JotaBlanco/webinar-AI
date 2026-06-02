# notes.md — m5-friction-circle

- rung: 3
- parent: m1-linear-dynamic-st
- status: drafting

## What this differs from

- **m1-linear-dynamic-st (parent):** M1 treats lateral and longitudinal
  tire forces as independent — `F_y = -C_α α` no matter what the tire
  is doing longitudinally. M5 keeps M1's linear demanded F_y but caps
  each axle's `F_y` to the *friction-circle envelope* once a fraction
  of grip is consumed by `a_long_mps2`. The extra parameters are
  `μ_f, μ_r, drive_split_front, brake_split_front`; static F_z per axle
  comes from `axle_load_static`. Below `|a_long| ≈ 0` the model
  collapses back to M1 exactly.
- **v1 (kinematic baseline):** V1 has no longitudinal coupling at all —
  it produces yaw rate algebraically from `(δ, v)` and ignores
  `a_long_mps2` / `brake_pressed` entirely. M5 is the first rung that
  uses those signals to *physically* explain residual yaw error in
  segments where the driver is braking into a corner or accelerating
  out of one.

## What residual symptom this targets

Yaw / CTE residual concentrated in **brake-in-corner** and **accel-out**
segments — anywhere `brake_pressed=1` or `|a_long_mps2| > 1.5 m/s²`
overlaps with non-trivial steering input. M5 should leave the
cruising-and-steady-state residual unchanged (collapses to M1 there) but
remove the systematic "tire over-promised lateral force during heavy
braking" pattern V1 and M1 both have.
