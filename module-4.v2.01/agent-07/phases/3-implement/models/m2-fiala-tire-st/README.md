# M2 — Nonlinear-tire (Fiala) single-track

Rung 2 of the dynamics ladder. Same `[β, ψ̇]` state and RK4 integration
as M1, but the linear tire force is replaced by the Fiala
piecewise-saturating curve. The minimum addition to make the model
honour the friction limit.

## Equations

```
α_f = β + l_f ψ̇ / v − δ
α_r = β − l_r ψ̇ / v
α_sl = atan(3 μ F_z / C_α)
F_y  = -C_α tan(α)          if |α| < α_sl
     = -sign(α) · μ F_z      otherwise
β̇  = (F_yf + F_yr) / (m v) − ψ̇
ψ̈  = (l_f F_yf − l_r F_yr) / I_z
```

State: `[β, ψ̇]`. Input: `δ` (road-wheel angle), `v` (measured longitudinal
speed). RK4 step. Reduces to V0 passthrough at `v < V_MIN_DYNAMIC = 4 m/s`.
Single tire per axle — axle-total `F_z`, axle-total `C_α`. Per-wheel
load-transfer split is M3.

## Parameters (per platform)

Fitted: `C_αf`, `C_αr`, `I_z`, `μ_f`, `μ_r` (five). Held from carParams:
`m`, `l_f`, `l_r`, `g`. Derived inside `predict_factory` (NOT fitted):
`F_zf, F_zr = axle_load_static(m, l_f, l_r, g)`.

Initial guess (in `coeffs.json`) seeded from
`_shared/physics_core.VEHICLE_PRIORS`:

| platform        | C_αf (N/rad) | C_αr (N/rad) | I_z (kg·m²) | μ_f, μ_r |
| --------------- | ------------ | ------------ | ----------- | -------- |
| F150 Lightning  | 378 307      | 469 878      | 9 903.37    | 0.95     |
| Mustang Mach-E  | 286 551      | 355 912      | 4 879.05    | 1.00     |
| Hyundai Ioniq 5 | 240 000      | 360 000      | 4 000.00    | 1.00     |

Bounds applied by `fit.py --with-bounds`: `C_α ∈ [0.3, 3.0] × prior`,
`I_z ∈ [0.5, 2.0] × prior`, `μ_{f,r} ∈ [0.7, 1.2]`. Default is
Nelder-Mead (no bounds), matching M1.

## Run

```
python fit.py                    # writes coeffs.json (default --max-iter 60)
python eval.py                   # writes scorecard.json against dev
python validate.py               # train→dev gap
python validate.py --final       # adds held-out test (preflight only)
```

Each script is independent — `eval.py` reads whatever is in `coeffs.json`,
so you can iterate by hand-editing coefficients (e.g. drop μ_f to 0.85
on F150) and re-running eval without refitting.

## When this helps

- High-`|a_lat|` dev segments where M1's yaw RMSE is much worse than
  its straight/steady-state RMSE — the signature of a model with no
  friction limit operating past it.
- Per-platform yaw-vs-δ "flat-top" — F150's was the original cohort
  finding (see `references/f150-yaw-ceiling.md`).
- Bias_warnings lit on Mach-E mid-sweepers where the rear axle is the
  one approaching α_sl.

## Failure modes

- **μ stuck on bound.** Fit pushes μ_f or μ_r to 0.7 or 1.2 → the data
  isn't constraining it, usually because the platform never operates
  in saturation in the train split. Symptom-only fix: reduce the
  bound or hold μ at the prior.
- **μ_f ≈ μ_r collapse.** Both legs converge to the same value and
  C_α picks up the asymmetry. Identifiability issue when slip on the
  two axles is correlated; consider sharing one μ and refitting.
- **F150 yaw still flat after M2.** Fiala saturation at the axle
  level can't represent inner-wheel unloading on a high-CG truck —
  the next rung is M3 (per-wheel load transfer), not more knobs on M2.
- **CTE regresses while yaw improves.** Same over-fit risk as M1, made
  worse by the two extra params. Drop to `--objective yaw_plus_cte`
  or shrink bounds.

## Iteration ideas if M2 beats M1

- Promote to M3 (per-wheel `F_z` from lateral load transfer + friction
  circle) — the cleanest next rung for F150.
- Combine the Fiala tire with M4's relaxation length (distance-based
  lag on top of saturation).
- Tie `μ_f = μ_r` and free up a parameter for `I_z` refit, if M2
  shows the μ-asymmetry isn't doing work.

## See

- `references/dynamics-formulations.md` § Rung 2.
- `references/f150-yaw-ceiling.md` — the original "flat-topping"
  diagnostic that motivated this rung.
