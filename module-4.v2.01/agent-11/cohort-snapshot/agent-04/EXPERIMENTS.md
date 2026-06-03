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
- Dev CV: yaw 0.00919 (priors only, fit did not converge in wall-clock budget), CTE 116.89
- vs V1: yaw -69%, CTE -124% (at priors — not reflective of a fit)
- Gate: fail (unfit-priors)
- Residual: structure_detected:F150-yaw-residual_mean=+0.0057 (load-transfer leakage as expected)
- Verdict: shelve  →  next: rerun fit on a quiet machine with C_α ratio constraint; agent-04 was racing 5+ parallel cohort fits on the same CPU

### 2026-06-03T09:32 — m4-relaxation-length
- Parent: v1
- Rung: orthogonal
- Dev CV: yaw 0.005636, CTE 52.15  (σ grid-fit per platform: F150=0.3 m, MachE=0.5 m, Ioniq=0.3 m)
- vs V1: yaw -3.8%, CTE +0.13%
- Gate: pass
- Residual: noise_floor (per-platform yaw residual means all |·|<0.0015)
- Verdict: keep but do not promote  →  next: shelve as near-tie; relaxation length doesn't strictly dominate V1 on either KPI. Fitted σ values (0.3–0.5 m) are within the public-spec band, so the null-ish result is consistent with the dataset already being phase-aligned by V1's τ.

### 2026-06-03T09:35 — v1-baseline-shipped (shipped candidate)
- Parent: v1
- Rung: 0
- Dev CV: yaw 0.005430, CTE 52.215
- vs V1: yaw 0.0%, CTE 0.0% (this IS the V1 shape)
- Gate: pass
- Residual: noise_floor
- Verdict: ship  →  next: final-model/predict.py
