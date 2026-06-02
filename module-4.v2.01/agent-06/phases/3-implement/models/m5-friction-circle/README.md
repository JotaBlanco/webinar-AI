# M5 — Long-lat coupled single-track with friction circle

Rung 3 (variant) of the dynamics ladder. Builds on M1's two-state linear
dynamic single-track by capping each axle's lateral force at the
friction-circle envelope when longitudinal force is consumed by accel or
braking. The first model on the ladder that actively uses
`a_long_mps2` and `brake_pressed`.

## Equations

```
F_x_total = m · a_long_mps2

if brake_pressed:
    F_xf = brake_split_front · F_x_total
    F_xr = (1 − brake_split_front) · F_x_total
else:
    F_xf = drive_split_front · F_x_total
    F_xr = (1 − drive_split_front) · F_x_total

α_f = β + l_f ψ̇ / v − δ
α_r = β − l_r ψ̇ / v
F_yf_demand = -C_αf α_f
F_yr_demand = -C_αr α_r

F_yf = friction_circle_cap(F_yf_demand, F_xf, μ_f, F_zf_static)
F_yr = friction_circle_cap(F_yr_demand, F_xr, μ_r, F_zr_static)

β̇  = (F_yf + F_yr) / (m v) − ψ̇
ψ̈  = (l_f F_yf − l_r F_yr) / I_z
```

State: `[β, ψ̇]`. Inputs: `δ, v, a_long_mps2, brake_pressed`. RK4 step.
Reduces to V0 passthrough at `v < 4 m/s`. Axle F_z comes from
`axle_load_static(m, l_f, l_r, g)` — total per axle, not per wheel.

## Parameters (per platform)

Fitted: `C_αf`, `C_αr`, `I_z`, `μ_f`, `μ_r`, `drive_split_front`,
`brake_split_front` — seven knobs. Held from carParams: `m`, `l_f`,
`l_r`, `g`. AWD prior `drive_split_front = 0.5` (all three trucks in
this dataset are AWD). Brake bias prior `brake_split_front = 0.6`
(standard front-heavy).

Bounds applied by `fit.py --with-bounds`: `C_α ∈ [0.3, 3.0] × prior`,
`I_z ∈ [0.5, 2.0] × prior`, `μ ∈ [0.7, 1.2]`, `drive_split ∈ [0.2, 0.8]`,
`brake_split ∈ [0.4, 0.8]`. Default optimiser is Nelder-Mead.

## Run

```
python fit.py                    # writes coeffs.json
python eval.py                   # writes scorecard.json against dev
python validate.py               # train→dev gap
python validate.py --final       # adds held-out test (preflight only)
```

Each script is independent — `eval.py` reads whatever is in `coeffs.json`,
so you can iterate by hand-editing coefficients and re-running eval
without refitting.

## When this helps

- Residual concentrated in segments with `brake_pressed=1` or
  `|a_long_mps2| > 1.5 m/s²` (the long-lat coupled regime).
- Per-platform `bias_warnings` lit on heavy-braking cornering segments
  where M1 predicts more yaw than the truth shows (tire can't deliver
  both `F_x` and `F_y_demand` simultaneously).
- F150 specifically — high CG and high mass mean the friction envelope
  saturates earlier than the lighter Mach-E / Ioniq.

## Failure modes

- Improvement visible on only a few segments. Most cruising data has
  small `a_long_mps2`, so the friction cap is rarely binding and the
  model collapses to M1 — pooled-dev RMSE moves a millihertz at best.
  Mitigation: segment-level evaluation; look at `brake_pressed=1`
  subset, not pooled mean.
- CTE regresses globally. The friction cap is a hard `min()` and
  introduces a discontinuity in F_y vs. `a_long` — RK4 spends a few
  steps oscillating near the boundary. Mitigation: replace `min` with
  a soft-min (smooth maximum, e.g.
  `F_y = F_max · tanh(F_y_demand / F_max)`).
- `μ_f`, `μ_r`, and `drive_split_front` jointly non-identifiable when
  most data is below the saturation boundary. Fit will report
  `co_collapse`. Mitigation: freeze `drive_split_front = 0.5` (AWD
  prior) and fit only `μ`.

## Iteration ideas if M5 beats M1

- Stack with M3's load transfer — replace static F_z with the
  load-transfer-aware F_z per axle. Then the friction circle shrinks on
  the inside wheel during a turn, which is the actually-correct picture.
- Add a longitudinal slip state and use Fiala for both `F_x` and `F_y`
  (full combined-slip tire). Heavier and probably overkill.
- Replace the hard cap with a smooth blend; rerun.

## See

- `references/dynamics-formulations.md` § Rung 3 (variant) — friction circle.
