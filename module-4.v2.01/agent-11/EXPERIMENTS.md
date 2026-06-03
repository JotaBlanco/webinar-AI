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

### 2026-06-03 — v1-baseline-leader
- Parent: v1
- Rung: 0
- Dev CV: yaw 0.007048, CTE 69.95
- vs V1: 0% / 0% (this IS V1)
- Gate: pass
- Residual: structure_detected: F150 CTE +29m signed drift documented in cohort findings
- Verdict: keep  →  next: explore additive corrections that don't break V1 structure

### 2026-06-03 — v1plus-joint-fit (g, K_us, tau per platform)
- Parent: v1-baseline-leader
- Rung: 0
- Dev CV: F150 yaw 0.00780 (+3.4%), MachE yaw 0.00817 (-1.2%), Ioniq yaw 0.00649 (~0%)
- vs V1: F150 yaw regresses on dev (overfit)
- Gate: warn (F150 dev regression)
- Residual: noise_floor on Ioniq, structure remains on F150
- Verdict: shelve — F150 needs different structure, not tighter fit  →  next: a_lat-based correction

### 2026-06-03 — m4-relaxation-length-fit
- Parent: v1
- Rung: orthogonal
- Dev CV: yaw 0.007211 (+2.3%), CTE 69.85 (-0.1%)
- vs V1: yaw worse, CTE noise-tied
- Gate: warn
- Residual: same shape as V1 — σ tuned to give identical lag as V1 τ at typical v
- Verdict: shelve  →  next: confirms cohort finding (V1 τ ≈ σ/v at highway speeds)

### 2026-06-03 — v1-loadtransfer-correction (SHIPPED)
- Parent: v1-baseline-leader
- Rung: 1
- Dev CV: yaw 0.007021 (-0.38%), CTE 69.4304 (-0.74%)
- Test (held-out): yaw 0.007159 (-0.39% vs V1 0.007187), CTE 65.69 (-0.55% vs V1 66.05)
- vs V1: yaw -0.38%, CTE -0.74% pooled; F150 dev CTE -3.4% (93.77→90.62)
- Gate: pass — improves on both KPIs on dev AND on held-out test, on all three platforms with truth
- Residual: F150 a_lat-correlated bias partially captured; further structure remains in load-transfer regime
- Verdict: promote_to_leader, shipped at final-model/  →  next: pursue M3 (double-track + load transfer) with these load-transfer coefficients as warm start
