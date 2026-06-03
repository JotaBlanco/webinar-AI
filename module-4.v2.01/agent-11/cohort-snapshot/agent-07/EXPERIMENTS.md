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

### 2026-06-03 — m4-relaxation-length (default σ=0.5)
- Parent: v1
- Rung: orthogonal
- Dev pooled: yaw 0.005854, CTE 52.13
- vs V1: yaw +0.4%, CTE +8.2%
- Gate: warn (near-tie at default; needs fit)
- Residual: structure_detected — F150 wide_train_dev_gap reappears on σ tuning
- Verdict: promote_to_leader → next: fit σ on yaw objective.

### 2026-06-03 — m4-relax-yawfit
- Parent: m4-relaxation-length
- Rung: orthogonal
- Dev pooled: yaw 0.005634, CTE 52.105
- vs V1: yaw +4.1%, CTE +8.3%
- Gate: pass (with F150 wide_train_dev_gap warning, +62%)
- Residual: structure_detected — F150 ceiling persists; load-transfer (rung 3 M3) is the likely fix.
- Verdict: ship → next: final-model/.

### 2026-06-03 — m1-linear-dynamic-st (rung-1 climb attempt)
- Parent: v1
- Rung: 1
- Dev pooled at priors: yaw 0.009192, CTE 116.89
- vs V1: yaw -56%, CTE -106% (UNFIT priors — not a fair comparison)
- Gate: fail (priors only; fit did not converge in 45-min budget)
- Residual: not assessed — fit incomplete.
- Verdict: shelve → next: would need vectorised RK4 or coarser train subset to be tractable. Logged as the cohort's 91st rung-1 climb attempt; consistent with prior 90 in failing to ship.

