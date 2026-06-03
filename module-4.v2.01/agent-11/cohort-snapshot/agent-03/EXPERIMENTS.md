# EXPERIMENTS.md

Append-only log of approaches you tried. One entry per concrete attempt. See `references/exploration-discipline.md` for the why.

In m4, **most entries are auto-appended by `skills/iterate/`** — each call
to iterate writes one entry per scored candidate. You append hand-written
entries only for things iterate didn't score (e.g. a decision to *not*
build a candidate, or a structural observation worth recording).

Schema (auto-filled by iterate; required on hand entries):

```
### <timestamp> — <model-name>
- Parent: <parent-model-name-or-v1>  |  Rung: 0 | 1 | 2 | 3 | orthogonal
- Dev CV: yaw <mean ± σ>, CTE <mean ± σ>
- vs V1: yaw <±N%>, CTE <±N%>
- Gate: pass | warn (reasons) | fail (reasons)
- Residual: noise_floor | structure_detected:<reason>
- Verdict: keep | shelve | promote_to_leader  →  next: <routing-string>
```

The `Parent:` field is m4's tree linkage — every entry points at the parent
candidate it was built from (or `v1` for top-level candidates). Combined
with `TREE.json` this is what gives the search its structure.

**`Rung:` is required on every entry.** Preflight enforces ≥1 entry tagged
`Rung: 1`, `Rung: 2`, `Rung: 3`, or `Rung: orthogonal`. Past cohorts piled
up at rung 0 — see `AGENTS.md` § "The default workflow". Tagging discipline:

- `Rung: 0` — kinematic single-track (V0 shape): coefficient refinements, polynomial steering scale, per-segment δ₀, lag time-constant tuning. Anything that stays in `yr_ss = v · δ / (L + K · v²)` territory.
- `Rung: 1` — linear dynamic single-track with slip angles. State variables `vy`, `yr`; lateral force `F = C_α · α`. See `references/dynamics-formulations.md` § "Rung 1" for the minimum viable recipe.
- `Rung: 2` — nonlinear tyre (Pacejka, Fiala, brush) on top of rung 1.
- `Rung: 3` — multi-body / weight-transfer coupling.
- `Rung: orthogonal` — non-physics paths (residual ML on top of a physical prior, sensor-fusion / complementary filter, etc.).

Delete this header section once you start logging, but keep the schema close to mind.

---

<!-- iterate appends entries below this line. Do not edit by hand;
     edit notes.md and re-iterate instead. -->

### 2026-06-03T09:30 — m1-linear-dynamic-st
- Parent: v1
- Rung: 1
- Dev CV: yaw 0.00919 (priors, unfit), CTE 116.89 (priors, unfit)
- vs V1: yaw -56%, CTE -106%
- Gate: fail (unfit; L-BFGS-B converged at initial point with zero numerical gradient; Nelder-Mead did not converge within budget)
- Residual: structure_detected:underfit (yaw_residual_mean +5.7e-3 on F150)
- Verdict: shelve  →  next: longer Nelder-Mead horizon or per-platform cornering-stiffness sweep before refit

### 2026-06-03T09:35 — m4-relaxation-length
- Parent: v1
- Rung: orthogonal
- Dev CV: yaw 0.005634, CTE 52.10
- vs V1: yaw +3.7%, CTE -0.2%
- Gate: warn (slightly worse on yaw, marginally better CTE; net loss on equally-weighted KPI)
- Residual: noise_floor (signed CTE bias on F150 +29m persists from V1 — relaxation length does not address F150 ceiling)
- Verdict: shelve  →  next: combine sigma with per-platform K_us refinement, or drop in favour of V1

### 2026-06-03T09:40 — v1-shipped
- Parent: v1
- Rung: 0
- Dev CV: yaw 0.005430, CTE 52.22
- vs V1: yaw 0%, CTE 0% (reference)
- Gate: pass
- Residual: structure_detected:f150-yaw-ceiling (matches cohort-wide ~+21% F150 yaw plateau; requires rung-3 weight-transfer physics to crack)
- Verdict: promote_to_leader  →  next: shipped as final-model after rung-1/orthogonal climb attempts both failed to beat reference

### 2026-06-03T09:45 — v1-scaled (per-platform WLS yaw scalar)
- Parent: v1
- Rung: 0
- Dev CV: yaw 0.005595, CTE 53.06
- vs V1: yaw +3.0%, CTE +1.6%
- Gate: fail (worse on both KPIs)
- Residual: structure_detected:scale-not-the-fix (F150 fitted scale 0.996 ~ 1.0 — the +29m signed CTE drift on F150 is not a global gain error)
- Verdict: shelve  →  next: confirms F150 needs rung-3 not gain-correction
