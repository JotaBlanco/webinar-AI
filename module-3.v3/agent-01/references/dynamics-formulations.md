---
name: dynamics-formulations
description: A catalogue of vehicle lateral-dynamics formulations — equations, parameter lists, identifiability notes. Starts with V0 (kinematic single-track + understeer + first-order lag, what V1 wraps) and sketches the higher rungs (linear dynamic ST, nonlinear tyre, multi-body). Expected to grow as agents document what they ship.
when-to-load: When you are deciding what *shape* of model to try beyond V1. Re-load when you've shipped a new formulation and are ready to document it for the next agent.
load-cost: ~700 words at start; grows as agents append.
---

# Dynamics formulations

A catalogue of vehicle lateral-dynamics models in increasing structural complexity. Use it as a menu when deciding *what shape* of model to try.

**This doc deliberately stops at equations + parameter list + identifiability notes per rung.** No drop-in `predict()` scaffolds — those produced a row of identical failure reports in m3.v2 (everyone copied the scaffold, hit the same Euler-instability at the same priors, reverted). The choice of integrator, state-variable initialisation, and parameter-identifiability strategy is the work — not boilerplate. When you ship something past V1, append your formulation here following V0's shape so the next agent doesn't re-derive equations from scratch.

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

## Rung 1 — Linear dynamic single-track with slip angles

The first principled climb past V0/V1. Replaces the steady-state assumption with the actual lateral dynamics ODE. The m3.v2 cohort produced ten attempts at a "minimum viable" version of this rung; all reverted. Common failure modes: Euler instability at openpilot `C_α` priors at 20 ms sample rate; `C_αf` / `C_αr` unidentifiable when the data is straight-driving-dominated; rung-1 yaw RMSE worse than the rung-0 ceiling because rung-0 had `δ₀` correction and the rung-1 attempt didn't. None of these are theoretical reasons rung 1 can't beat V1 — they're implementation issues that the prior cohort didn't fix.

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

### Implementation notes — things to decide before writing the integrator

The implementation choices are the work; this list is a checklist, not a recipe:

- **State variables and initial condition.** `vy` and `yr`. Segments start mid-motion, so `vy[0] = 0` is a simplification — could fit `vy[0]` per segment from the first few rows, or warm-start from a low-pass-filtered V0 trajectory, or accept the transient.
- **Integrator.** Explicit Euler is unstable at openpilot `C_α` priors at 20 ms sample rate. Options: backward (implicit) Euler, RK4, sub-stepping, or refit `C_α` so the eigenvalues sit inside the explicit-Euler stability region.
- **`vx · yr` term in `vy_dot`** becomes near-singular at very low `vx`. Clamp, switch integrator, or filter the sample.
- **Identifiability.** `C_αf` and `C_αr` cannot both be observed independently without enough lateral-acceleration variation. If your dev data is dominated by straight-driving, fix one, constrain the ratio from carParams, or use a regularised fit.
- **Composition with V1.** Rung-1 dynamics is orthogonal to the V1 `δ₀` correction — you can keep the per-segment `δ₀` layer in front of the rung-1 integrator. A rung-1 attempt that *drops* the `δ₀` correction is competing against V0, not V1.
- **Fittable parameter set.** Naive list is `{C_αf, C_αr, m, Iz, a, b}`. Fixing `{m, Iz, a, b}` from carParams and fitting only `{C_αf, C_αr}` is cheap but the carParams `Iz` is itself crude — sensitive parameter, may need a third fit knob.

### When this helps

- Transient regime carries >50% of residual yaw RMSE on a platform.
- High-frequency yaw oscillations the first-order lag in V0 can't follow (visible in `inspect-residuals` plots vs time).

### Failure modes

- `C_αf` / `C_αr` fit to bizarre values — under-constrained; fix one or bound to `carParams ± 50%`.
- Integrator unstable at low `vx` — clamp.
- Trajectory CTE worse despite better yaw RMSE — model is over-fit; re-check on dev, reduce parameter count.

---

## Rung 2 — Nonlinear tyre on top of rung 1 *[sketch — not implemented]*

Replaces the linear `F = C_α · α` with a saturating curve.

### Pacejka magic formula (simplified, single axle)

```
F_y(α) = D · sin(C · atan(B · α − E · (B · α − atan(B · α))))
```

`B, C, D, E` per axle. `D` is peak force. Powerful but fitting 8 parameters per platform is risky without enough high-`a_lat` variation.

### Fiala (simpler, easier to fit)

```
α_sl  = atan(3 · μ · F_z / C_α)            # slip angle at full saturation
F_y(α) = C_α · tan(α)  if |α| < α_sl
       = ±μ · F_z       otherwise           # piecewise linear-to-saturation
```

Three params per axle (`C_α`, `μ`, `F_z`). `F_z` derivable from vehicle mass and weight distribution; `μ` is the road-friction coefficient (~0.8–1.0 dry asphalt).

### Brush model
Single parameter `μ`; saturates more abruptly than Pacejka. Cheapest nonlinear option.

### When to climb to rung 2

After rung 1, **only if** the residual is concentrated in high-`|a_lat|` segments. Use the allowlist proxy `|a_lat| ≈ |v_mps * yaw_rate_pred_rads| > 4` to identify them (`a_lat_meas_mps2` is denied at grading — see `AGENTS.md` § Operating contract). If your data doesn't push tyres into saturation, the cheaper Fiala or staying on rung 1 wins.

### Failure modes

- Pacejka coefficients converge to silly values — data doesn't have enough saturation; switch to Fiala or stay on rung 1.
- Front-axle and rear-axle tyres get the same parameters by accident — they're different cars-worth of weight; fit independently.

---

## Rung 3 — Multi-body with load transfer *[sketch — probably overkill for this dataset]*

Couples longitudinal accel (`a_long_mps2`) into lateral via load transfer, which modulates the effective `C_α` per axle dynamically. Theoretically clean but probably not worth it on this dataset because `v` is clamped to measured (longitudinal dynamics partly removed).

Listed for completeness. If you reach for this, document it here.

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
