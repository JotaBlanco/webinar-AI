# M1 — Linear dynamic single-track (LDST)

Rung 1 of the dynamics ladder. Two-state ODE for sideslip and yaw rate;
linear tires. The canonical "next step past kinematic," referenced in
every cohort retro but never shipped.

## Equations

```
α_f = β + l_f ψ̇ / v − δ
α_r = β − l_r ψ̇ / v
F_yf = -C_αf α_f
F_yr = -C_αr α_r
β̇  = (F_yf + F_yr) / (m v) − ψ̇
ψ̈  = (l_f F_yf − l_r F_yr) / I_z
```

State: `[β, ψ̇]`. Input: `δ` (road-wheel angle), `v` (measured longitudinal
speed). RK4 step. Reduces to V0 passthrough at `v < 1.5 m/s`.

## Parameters (per platform)

Fitted: `C_αf`, `C_αr`, `I_z`. Held from carParams: `m`, `l_f`, `l_r`.

Initial guess (in `coeffs.json`) seeded from
`_shared/physics_core.VEHICLE_PRIORS`. Ioniq priors are public-spec
estimates and are the most likely to need fitting.

Bounds applied by `fit.py` by default: `C_α ∈ [0.3, 3.0] × prior`,
`I_z ∈ [0.5, 2.0] × prior`. Pass `--no-bounds` to use Nelder-Mead.

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

- Pooled-dev yaw shows transient-regime residual >> straight/steady.
- V1's per-platform signed yaw bias is non-zero (bias_warnings lit).
- Phase-lag artifacts visible in `inspect-residuals` time plots.

## Failure modes

- `C_αf` ↔ `C_αr` non-identifiable (low `a_lat` variation). Fit will
  warn `co_collapse` or `stuck_on_bound`. Mitigation: fix `C_αr` from
  carParams, fit only `C_αf`, or constrain their ratio.
- `I_z` fits to bound. Often acceptable on Ioniq (estimated prior); on
  F150 means the load-transfer story (M3) is leaking into the inertia.
- CTE regresses while yaw improves. Over-fit; reduce parameter count
  or shrink bounds.

## Iteration ideas if M1 beats V1

- Add a tunable lag `τ` on top of M1 (often goes to 0 — null result
  confirms the dynamic model already captures the lag).
- Combine with M4's relaxation length (replaces `τ` with distance-based
  lag).
- Add per-segment δ₀ if Mach-E shows residual bias.

## See

- `references/dynamics-formulations.md` § Rung 1.
- `references/m4-cohort-findings.md` § 1 — "the rung nobody climbed."
