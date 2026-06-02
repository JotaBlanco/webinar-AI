---
name: dynamics-formulations
description: A growing catalogue of vehicle lateral-dynamics formulations the agent can pick from when choosing what model to fit. Starts with V0 documented in full (rung 0 — kinematic single-track + understeer + first-order lag) and sketches the higher rungs (linear dynamic ST, nonlinear tyre, multi-body). Expected to grow — when you ship a new formulation, append a section here so the next agent can build on your work.
when-to-load: At the start, paired with `approach-menu.md` § "Physics-based options — a ladder", when you're choosing what model to fit. Re-load when you've climbed a rung and are ready to document what you found.
load-cost: ~900 words at start; grows as agents append.
---

# Dynamics formulations

A catalogue of vehicle lateral-dynamics models in increasing structural complexity. Use it as a menu when deciding *what shape* of model to fit (`approach-menu.md` covers when to climb vs refine; this doc covers *what* you'd climb to).

**This doc is designed to grow.** V0 is documented in full because every agent starts there. Rungs 1–3 are sketched — equations, parameter lists, implementation notes — but not implemented. When you ship something past V0, append your worked formulation here following V0's shape. The next agent shouldn't have to re-derive the slip-angle equations from scratch.

---

## V0 — Kinematic single-track with steady-state understeer + first-order yaw lag *[shipped, this is the baseline]*

### Equations

```
steady-state yaw rate:    yr_ss = v · δ / (L_eff + K_us · v²)
                          where δ = (delta_road_rad − δ₀) · g

first-order lag:          yr[i+1] = yr[i] + α · (yr_ss[i] − yr[i])
                          where α = dt / (τ + dt)

trajectory:               Euler integration of (v_meas, yr) from (0, 0, 0)
                          (see _shared/traj_metrics.integrate_trajectory)
```

### Parameters (per platform)

| param | meaning | typical | source for initial guess |
|---|---|---|---|
| `L_eff` | effective wheelbase (m) | ~2.85 (Mach-E) / ~3.7 (Lightning) | `code/parameters.py` (carParams) |
| `g` | steering scale | ~0.86–0.89 | fit from data |
| `δ₀` | steering offset (rad) | -0.0001 to 0.0013 | fit (per-segment for Mach-E, global for Lightning — see `anti-patterns.md`) |
| `K_us` | understeer coefficient (s²/m) | ~0.002–0.0035 | fit |
| `τ` | first-order lag time constant (s) | ~0.06–0.07 | fit |

### Known limitations

- **Steady-state.** Doesn't model transient slip dynamics; the first-order lag with `τ` is a band-aid for the missing transient.
- **Linear tyre.** No saturation at high `a_lat`.
- **Single-axis.** No lateral-longitudinal coupling.
- **Constant `K_us`.** Real understeer drifts with `a_lat` and tyre wear.

### When V0's ceiling shows

Use `scoring-model`'s per-regime breakdown to diagnose:
- Residual concentrated in **transient** regime (`|d(delta)/dt| > 0.05`) → first-order lag is failing to fit the dynamics. Climb to rung 1.
- Residual concentrated in **high-`a_lat`** segments → linear tyre is saturating. Climb to rung 2 (probably after rung 1).
- Residual concentrated in **straight** regime → bias source (δ₀ trick territory) — stay on rung 0.

---

## Rung 1 — Linear dynamic single-track with slip angles *[the default climb attempt — see AGENTS.md § "On exploration"]*

The first principled climb past V0. Replaces the steady-state assumption with the actual lateral dynamics ODE. **This is the rung your `EXPERIMENTS.md` is required to contain at least one attempt at** — the cohort needs evidence about whether it pays on this data, and we don't have that evidence yet.

### Equations

```
front slip angle:   α_f = δ − (vy + a · yr) / vx
rear slip angle:    α_r = −(vy − b · yr) / vx

lateral forces:     F_yf = C_αf · α_f
                    F_yr = C_αr · α_r

state derivatives:  vy_dot = (F_yf + F_yr) / m − vx · yr
                    yr_dot = (a · F_yf − b · F_yr) / Iz

trajectory:         Euler/RK4 integration of (vx, vy, yr)
```

Where `vx = v_mps` (longitudinal speed, measured), `vy` is lateral velocity (a state, initialised at 0), `a` and `b` are distances from CG to the front/rear axle with `a + b = L_eff`.

### Parameters needed (per platform)

| param | meaning | source for initial guess |
|---|---|---|
| `C_αf`, `C_αr` | front/rear cornering stiffness (N/rad) | `code/parameters.py` — **known to be off; fit from data** |
| `m` | vehicle mass (kg) | `code/parameters.py` |
| `Iz` | yaw moment of inertia (kg·m²) | `code/parameters.py` (often a crude estimate; sensitive parameter) |
| `a`, `b` | CG-to-axle distances (m) | carParams (verify `a + b == L_eff`) |
| `τ` | optional first-order lag on top | fit, may go to zero |

### Minimum viable rung-1 attempt — ~30 lines, two fitted params

You do NOT have to fit all of `{C_αf, C_αr, m, Iz, a, b}`. The cheap version: fix `m`, `Iz`, `a`, `b` from `code/parameters.py` (carParams), fix `C_αr` from carParams too, fit **only** `C_αf` per platform. That's two states (`vy`, `yr`), Euler integration, one fitted parameter. The expensive part is the integration loop, not the optimisation.

```python
import numpy as np
import pandas as pd

def _rung1_predict(sim_df: pd.DataFrame, p: dict) -> np.ndarray:
    """Linear dynamic single-track. p = {C_af, C_ar, m, Iz, a, b}.
    Returns yaw_rate aligned with sim_df.index."""
    delta = sim_df["delta_road_rad"].to_numpy()
    vx    = sim_df["v_mps"].to_numpy()
    t     = sim_df["t_s"].to_numpy()

    vx_safe = np.maximum(vx, 1.0)         # clamp to avoid /0 in slip-angle
    dt = np.diff(t, prepend=t[0])

    C_af, C_ar = p["C_af"], p["C_ar"]
    m, Iz       = p["m"], p["Iz"]
    a, b        = p["a"], p["b"]

    vy = 0.0                              # state init
    yr = 0.0
    out = np.empty_like(vx)
    for i in range(len(vx)):
        alpha_f = delta[i] - (vy + a * yr) / vx_safe[i]
        alpha_r =           -(vy - b * yr) / vx_safe[i]
        F_yf = C_af * alpha_f
        F_yr = C_ar * alpha_r
        vy_dot = (F_yf + F_yr) / m - vx[i] * yr
        yr_dot = (a * F_yf - b * F_yr) / Iz
        vy += vy_dot * dt[i]
        yr += yr_dot * dt[i]
        out[i] = yr
    return out
```

Wrap that in a `predict_factory(platform, coeffs)` (see `fit-model`'s SKILL.md), seed `C_af` from carParams (e.g. ~80,000 N/rad for the Fords), bound it to `(20_000, 200_000)`, and let `fit-model` go. Per platform. Total time: an hour if you've never written this before, much less if you have. Even if it doesn't beat your rung-0 model, **log it under `Rung: 1` in `EXPERIMENTS.md`** — that is the required deliverable. Past cohorts assumed this was a 50-100 line lift; it's 30 lines and one fitted parameter.

### Implementation notes (when you build this)

- Two integration states: `vy`, `yr`. Use the same dt-step Euler as V0 — start simple. Upgrade to RK4 only if you see instability at low `vx`.
- Initial condition `vy[0] = 0` is a small simplification (segments often start mid-motion). Could fit `vy[0]` per segment from a few rows, or ignore.
- `vx · yr` term in `vy_dot` becomes near-singular at very low `vx`; clamp `vx > 1.0` or use implicit step.
- Use `fit-model` with the coefficient dict `{C_af, C_ar, m, Iz, a, b}`. Per-platform.
- **Identifiability warning**: `C_αf` and `C_αr` cannot both be observed independently without enough lateral-acceleration variation. If your dev data is dominated by straight-driving, fix one or constrain the ratio from `carParams`.

### When this helps

- Transient regime carries >50% of residual yaw RMSE on a platform.
- High-frequency yaw oscillations the first-order lag in V0 can't follow (visible in `inspect-residuals` plots vs time).

### Failure modes

- `C_αf` / `C_αr` fit to bizarre values — under-constrained; fix one or bound to `carParams ± 50%`.
- Integrator unstable at low `vx` — clamp.
- Trajectory CTE worse despite better yaw RMSE — model is over-fit; re-check on dev, reduce parameter count.

---

## Rung 2 — Nonlinear-tire single-track (Fiala) *[prefilled as M2]*

Replaces the linear `F_y = -C_α α` from rung 1 with the **Fiala
piecewise-saturating** curve. Same `[β, ψ̇]` state; same RK4 integrator;
the only change is the tire-force law and the addition of `μ` and the
static `F_z` per axle.

### Equations

```
α_sl  = atan(3 μ F_z / C_α)
F_y   = -C_α tan(α)             if |α| < α_sl
F_y   = -sign(α) μ F_z           otherwise

state derivatives  (same as rung 1):
  β̇   = (F_yf + F_yr) / (m vx) − ψ̇
  ψ̈   = (l_f F_yf − l_r F_yr) / I_z
```

### Parameters (per platform)

| param | meaning | source |
|---|---|---|
| `m, l_f, l_r, I_z` | inherited from rung 1 | `code/parameters.py` |
| `C_αf, C_αr` | front / rear linear-region cornering stiffness | fit or carParams |
| `μ_f, μ_r` | tire-road friction per axle | fit, bounded `[0.7, 1.2]` |
| `F_zf, F_zr` | static axle loads | derived from `m`, `l_f`, `l_r`, `g` |

Implementation lives in `_shared/physics_core.py::fy_fiala`. Five
fitted parameters per platform (`C_αf, C_αr, μ_f, μ_r`, and optionally
`Iz`).

### When this helps

- Residual concentrated in segments where `|v · yr| > 4 m/s²` (high
  lateral acceleration proxy — the truth column is denied at grading).
- V1 over-predicts yaw on high-G sweepers (sign of unsaturated tire
  model overshooting at the limit).

### Failure modes

- `μ` fits to bound at 0.7 or 1.2 — your dataset doesn't have enough
  saturation to identify it; fix `μ = 1.0` and fit only `C_α`.
- `μ_f` and `μ_r` collapse together — under-constrained; fit a single
  global `μ` instead.
- F150 still flat — saturation isn't its primary problem; M3 is the
  right next rung.

### Prefilled at

`phases/3-implement/models/m2-fiala-tire-st/`. Run
`python fit.py && python eval.py` for a working scorecard.

---

## Rung 3 — Double-track with lateral load transfer *[prefilled as M3]*

The first model that splits each axle into two wheels with **separate
normal loads** modulated by quasi-static lateral load transfer. Targets
the F150 yaw ceiling directly (see `references/f150-yaw-ceiling.md`).

### Equations

```
static axle loads:
  F_zf_static = m g l_r / L
  F_zr_static = m g l_f / L

steady lateral load transfer per axle:
  ΔF_z_axle = (F_z_axle / g) · a_y · h_cg / t_w
  F_z_inner = F_z_axle/2 − ΔF_z_axle        (≥ 0)
  F_z_outer = F_z_axle/2 + ΔF_z_axle

per-wheel tire force (Fiala on each of the four):
  F_y_wheel = fiala(α_axle, C_α_axle/2, μ_axle, F_z_wheel)

axle force (summed):
  F_y_axle = F_y_inner + F_y_outer

state derivatives (single-track structure preserved at the axle level):
  β̇  = (F_yf + F_yr) / (m vx) − ψ̇
  ψ̈  = (l_f F_yf − l_r F_yr) / I_z

a_y for load transfer is solved iteratively (fixed point) per step
or proxied from the previous step's ψ̇·vx — see implementation notes.
```

### Parameters (per platform)

| param | meaning | source |
|---|---|---|
| inherits | rung-2 params | as before |
| `h_cg` | CG height (m) | `code/parameters.py` or fit |
| `t_w` | track width (m) | carParams or measured |

F150: `h_cg ≈ 0.74 m`, `t_w ≈ 1.71 m` (truck — large transfer at high `a_y`).
Sedan: `h_cg ≈ 0.55 m`, `t_w ≈ 1.62 m`.

### When this helps

- Sustained lateral acceleration on heavy or high-CG platforms (F150).
- V1's per-platform residual shows **signed yaw bias** (not just
  noise) at `a_y > 2 m/s²`.
- Asymmetric tire saturation visible — V1 fits OK in left turns and
  badly in right turns (or vice versa).

### Failure modes

- `h_cg` fits to a value far from carParams — fixed-point iteration on
  `a_y` is unstable; bound it `[0.4, 1.0]` and use a single
  predictor-corrector step rather than full iteration.
- Inner wheel `F_z` clamps to zero (truck on the limit) and the model
  becomes effectively a single-track again — by design; that's the
  physically-correct degenerate behaviour, but it kills the
  identifiability of `μ_r` on F150.
- CTE regresses on light/agile platforms (Mach-E) — model is overkill;
  use M3 only on F150, M2 on the others.

### Prefilled at

`phases/3-implement/models/m3-double-track-load-transfer/`.

---

## Orthogonal — Relaxation-length tire on kinematic *[prefilled as M4]*

Keeps V1's kinematic core, but replaces the time-domain first-order yaw
lag (`τ`) with a **distance-domain** first-order tire-force relaxation.
Tire lateral force takes a relaxation length `σ` of forward travel to
develop after a steering input — empirically supported in vehicle
dynamics literature (Pacejka §2, Mitschke §11). Cheap (one fitted
parameter per axle, or one global), orthogonal to the dynamics ladder.

### Equations

```
F_y_demand[k] = kinematic ψ̇ predicted by V1, mapped through C_α
F_y_state[k]  = F_y_state[k-1] + (1 − exp(−v·dt/σ)) · (F_y_demand[k] − F_y_state[k-1])
ψ̇_corrected   = (F_y_state / F_y_demand) · ψ̇_V1     (per-axle scale)
```

In practice we apply the relaxation to the steady-state yaw signal
itself:

```
yr_demand[k] = V1 steady-state yaw rate (existing)
yr[k] = yr[k-1] + (1 − exp(−v[k]·dt[k]/σ)) · (yr_demand[k] − yr[k-1])
```

At `v = constant`, this collapses to V1's first-order time lag with
`τ = σ / v` — i.e. the lag *shortens* as the car goes faster, which is
the physically correct behaviour (and is what V1's fixed `τ` gets wrong
across the speed range).

### Parameters

| param | meaning | typical |
|---|---|---|
| `sigma` | relaxation length (m) | 0.3 – 1.2 m |

Fit one `σ` per platform. Optionally per-axle if you split it.

### When this helps

- Residual shows **speed-dependent phase lag** — V1's `τ` fits well at
  one speed but the residual increases at high or low speed.
- Ramp-steer segments where V1 lags incorrectly.

### Failure modes

- `σ` fits to ~0 → relaxation collapses, model = V1. Acceptable null
  result; document and shelve.
- `σ` fits very large (≥ 3 m) → optimiser is masking a structural bug;
  bound `[0.05, 2.0]`.

### Prefilled at

`phases/3-implement/models/m4-relaxation-length/`.

---

## Rung 3 (variant) — Long-lat coupled with friction circle *[prefilled as M5]*

Couples longitudinal force (from `a_long_mps2` and tire load) into the
lateral envelope via the **friction circle**: a tire can produce up to
`μF_z` of combined force, so longitudinal usage steals from lateral
capacity. Uses M1's two-state vehicle dynamics, but caps `F_y` per axle
at the available envelope each step.

### Equations

```
F_x_axle  ≈ m · a_long_mps2 · (drive weight share)
F_y_max   = sqrt((μ F_z)² − F_x²)         per axle (zero if F_x ≥ μF_z)
F_y_demand = -C_α α                        (Fiala or linear)
F_y_axle   = sign(F_y_demand) · min(|F_y_demand|, F_y_max)

state derivatives  (same as rung 1, with capped F_y):
  β̇  = (F_yf + F_yr) / (m vx) − ψ̇
  ψ̈  = (l_f F_yf − l_r F_yr) / I_z
```

Distribution of `F_x` between front/rear: use a fixed `drive_split`
parameter (e.g. AWD ≈ 50/50, RWD = 0/1, FWD = 1/0). All three platforms
in this dataset are AWD, so 50/50 is a good prior. Brakes: when
`brake_pressed == 1`, assume 60 % front / 40 % rear distribution.

### Parameters (per platform)

| param | meaning |
|---|---|
| inherits | rung-1 / rung-2 params |
| `drive_split_accel` | F_x distribution during acceleration |
| `brake_split` | F_x distribution during braking |

### When this helps

- Residual concentrated in segments with `brake_pressed == 1` OR
  `|a_long_mps2| > 1.5 m/s²`.
- Yaw error spikes during corner entry (trail-braking) or corner
  exit (throttle-on).

### Failure modes

- Improvement only on a few segments — friction circle is an
  edge-of-envelope effect; if the dataset is mostly cruising
  (`|a_long| < 1`), the model collapses to M1.
- CTE regresses globally — capping `F_y` mid-corner can introduce
  discontinuities; smooth the cap with a soft-min if so.

### Prefilled at

`phases/3-implement/models/m5-friction-circle/`.

---

## How to extend this doc

When you ship a model that goes beyond V0, append a `## Rung N — <name> [shipped by you]` section using V0's shape:

1. **Equations** — plain math notation, no LaTeX
2. **Parameter table** — name, meaning, units, source for initial guess
3. **Implementation notes** — gotchas you hit (numerical, identifiability, initialisation)
4. **When this helps** — symptom that points at this rung
5. **Failure modes** — what to watch for

Keep each section short — V0 above is ~150 words of prose + the equations + the table; that's the target. Long enough to be useful, short enough to be loaded.

If you tried a formulation that **didn't** work, add it under a `## Tried and shelved` heading with a one-paragraph note on why. That's as valuable as the wins — it stops the next agent re-trying the same dead end.

---

## Tried and shelved

*(none yet — be the first to add one)*

---

## Failure-mode index — formulation pitfalls

| You'll see this if... | What it points to |
|---|---|
| You're fitting `C_αf` and `C_αr` but `a_lat` in your data barely varies | parameters un-identifiable — constrain ratio or fix one to `carParams` |
| Your dynamic-ST CTE is worse than V0 despite better yaw RMSE | over-fit; check dev split, reduce parameter count, simplify back to rung 1 |
| Pacejka coefficients converge to silly values | tyres aren't being driven into saturation; cheaper Fiala or stay on rung 1 |
| You skipped rung 1 and went straight to rung 2 | not necessarily wrong, but you skipped the diagnostic — re-check whether the residual demands nonlinear tyre |
| Integrator goes unstable at low `vx` | clamp `vx > 1.0` or use implicit step |
| You started writing dynamics from scratch without checking this doc | the next agent will redo your work — append your formulation here when you're done |
