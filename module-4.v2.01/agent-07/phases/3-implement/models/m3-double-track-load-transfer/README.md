# M3 — Double-track with lateral load transfer

Rung 3 of the dynamics ladder. The body equations are still single-track
(`[β, ψ̇]`), but each axle is now split into an inner and outer wheel:
quasi-static lateral load transfer reshapes the per-wheel `F_z` from
`a_y ≈ v · ψ̇`, then Fiala is evaluated independently on each wheel with
half the axle stiffness. This is the rung targeted at the F150 yaw
ceiling — see `references/f150-yaw-ceiling.md`.

## Equations

```
α_f = β + l_f ψ̇ / v − δ
α_r = β − l_r ψ̇ / v
a_y ≈ v · ψ̇                    (current-state proxy)

F_zf_static, F_zr_static = axle_load_static(m, l_f, l_r, g)

per axle:
  F_z_inner, F_z_outer = lateral_load_transfer(F_z_axle, a_y, h_cg, t_w, g)
  F_y_axle = fy_fiala(α, C_α/2, μ, F_z_inner)
           + fy_fiala(α, C_α/2, μ, F_z_outer)

β̇  = (F_yf + F_yr) / (m v) − ψ̇
ψ̈  = (l_f F_yf − l_r F_yr) / I_z
```

State: `[β, ψ̇]`. Input: `δ` (road-wheel angle), `v` (measured
longitudinal speed). RK4 step. Reduces to V0 passthrough at
`v < V_MIN_DYNAMIC` (= 4 m/s).

## Parameters (per platform)

Fitted: `C_αf`, `C_αr`, `I_z`, `μ_f`, `μ_r`, `h_cg`. Held from
carParams: `m`, `l_f`, `l_r`, `t_w`, `g`. The static per-axle totals
`F_zf`, `F_zr` are derived from `(m, l_f, l_r, g)` inside the predict
factory, not fitted.

Initial guess (in `coeffs.json`) seeded from
`_shared/physics_core.VEHICLE_PRIORS`. F150 carries h_cg=0.74 (high
truck), t_w=1.71; Mach-E h_cg=0.55, t_w=1.62; Ioniq h_cg=0.58, t_w=1.63.

Bounds applied by `fit.py --with-bounds`: `C_α ∈ [0.3, 3.0] × prior`,
`I_z ∈ [0.5, 2.0] × prior`, `μ ∈ [0.7, 1.2]`, `h_cg ∈ [0.4, 1.0]`.
Default optimiser is Nelder-Mead.

## Run

```
python fit.py                    # writes coeffs.json
python eval.py                   # writes scorecard.json against dev
python validate.py               # train→dev gap
python validate.py --final       # adds held-out test (preflight only)
```

Each script is independent — `eval.py` reads whatever is in
`coeffs.json`, so you can iterate by hand-editing coefficients and
re-running eval without refitting.

## When this helps

- Heavy, high-CG vehicles at sustained lateral acceleration —
  the F150 sweeper regime is the canonical case.
- Per-platform yaw bias on the truck that survived M1 and M2; the
  per-axle-saturation story of M2 isn't enough because the inner/outer
  load split is what controls the effective axle stiffness on the limit.
- `bias_warnings` lit on F150 with the residual concentrated in
  `|a_lat| > 2 m/s²` segments.

## Failure modes

- **Inner-wheel `F_z` clamps to zero** at the limit. That's the
  physics — but it kills μ_r identifiability for the unloaded side
  whenever the agent fits on a route that lives there. Expect
  `stuck_on_bound` on μ_r for Mach-E / Ioniq if high-`a_lat` data is
  sparse.
- **CTE regresses on Mach-E.** M3 is overkill for a light, low-CG,
  agile vehicle — the load-transfer correction is small and the extra
  fitted parameters absorb noise. Use M3 only on F150; keep M1 or M2
  on Mach-E.
- **`I_z` drifts** if the model is also fitting `μ`. The yaw moment of
  inertia and the rear-axle saturation point are partially confounded
  on transient inputs; tightening the `I_z` bound is the usual fix.
- **Numerical chattering** if `a_y = ψ̇ · v` blows up. The
  `V_MIN_DYNAMIC` floor and `lateral_load_transfer`'s clipping to
  `F_z ≥ 0` handle this in practice; if it persists, switch to a
  previous-step ψ̇ predictor-corrector.

## Iteration ideas if M3 beats M2

- Add a tunable `t_w` (currently held at carParams) if the F150 fit
  pins `h_cg` at a bound.
- Combine with M4's relaxation length to capture transient lag on top
  of the steady-state load split.
- Move to a true 4-wheel body (`vy`, `ψ̇`, roll φ, roll rate) if the
  quasi-static load split leaves residual in fast left-right transitions.

## See

- `references/dynamics-formulations.md` § Rung 3 — double-track.
- `references/f150-yaw-ceiling.md` — the platform-specific motivation.
