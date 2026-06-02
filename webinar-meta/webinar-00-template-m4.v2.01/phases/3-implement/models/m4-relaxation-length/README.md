# M4 — Relaxation-length tire on kinematic core

Orthogonal rung. Keeps V1's kinematic single-track + understeer + per-
segment δ₀ unchanged, and replaces V1's time-domain first-order yaw lag
(`τ`) with a *distance-domain* first-order tire-force relaxation.

Tire lateral force takes a relaxation length `σ` (meters) of forward
travel to develop after a steering input. At constant `v` this is
equivalent to a first-order time lag with `τ = σ / v` — i.e. the lag
*shortens* as the car goes faster, which is the physically correct
behaviour V1's fixed `τ` gets wrong across the speed range.

## Equations

```
δ_eff      = (δ − δ₀) · g
yr_demand  = v · δ_eff / (L_eff + K_us · v²)        # V1 steady-state, unchanged
yr[k]      = yr[k-1] + (1 − exp(−v[k] · dt[k] / σ)) · (yr_demand[k] − yr[k-1])
```

V0 passthrough below `v < 1.5 m/s` (local M4 floor — the relaxation
filter has no 1/v singularity, so we go below physics_core's
`V_MIN_DYNAMIC = 4.0`).

## Parameters (per platform)

Fitted: `sigma` (relaxation length, meters). One per platform.

Held from V1 (constants of record — see `code/v1_baseline.py`): `g`,
`L_eff`, `K_us`, δ₀ policy. M4 does NOT fit V1's parameters; that's
what makes it orthogonal.

Initial guess (in `coeffs.json`) seeded at `σ = 0.5 m`, the midpoint of
the literature-typical 0.3–1.2 m band. Bounds applied by `fit.py` with
`--with-bounds`: `σ ∈ [0.05, 2.0]` m.

## Run

```
python fit.py                    # writes coeffs.json (merges)
python eval.py                   # writes scorecard.json against dev
python validate.py               # train→dev gap
python validate.py --final       # adds held-out test (preflight only)
```

Each script is independent — `eval.py` reads whatever is in `coeffs.json`,
so you can sweep `σ` by hand-editing and re-running eval without
refitting.

## When this helps

- V1's residual rises at very high *and* very low speed — a clean sign
  that a fixed `τ` cannot fit across the speed range.
- Ramp-steer segments where V1's lag is right at one speed and wrong at
  another.
- Per-platform `τ` tuning has plateau'd: same shape of residual returns
  after every refit.

## Failure modes

- `σ → 0` — relaxation collapses, M4 reduces to V1's no-lag baseline.
  Acceptable null result; document and shelve. Means the residual is
  not lag-dominated.
- `σ` very large (≥ 2 m, optimiser pinning the upper bound) — the lag
  parameter is masking a structural bug elsewhere (sign error, δ₀
  mismatch). Shrink the upper bound and investigate.
- CTE regresses while yaw improves — heading-integration drift from
  over-filtering. Switch to `--objective cte` or `yaw_plus_cte`.

## Iteration ideas if M4 beats V1

- Split `σ` per axle (front / rear) — two parameters, captures the
  front-load-transfer asymmetry.
- Compose M4 onto an LDST core (M1) — replace M1's V0 fallback with
  M4's σ-filtered V1.
- Per-platform σ vs cohort-pooled σ — test the platform-specificity.

## See

- `references/dynamics-formulations.md` § Orthogonal — relaxation-length.
- `code/v1_baseline.py` for the V1 constants M4 holds fixed.
