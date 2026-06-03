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

### 2026-06-03 — m1-linear-dynamic-st (prefilled, scored from scorecard)
- Parent: v1
- Rung: 1
- Dev pooled: yaw 0.009192, CTE 116.889 (frozen split, 402 segments)
- vs V1: yaw +56% (worse), CTE +106% (worse)
- Gate: fail (dev_obj > v1 by wide margin; per-platform F150 yaw_residual_mean=+0.0057 high)
- Residual: structure_detected:steady-state-cornering-stiffness-mismatch (C_alpha priors unfit)
- Verdict: shelve  →  next: would need joint fit of C_alpha_f/r + I_z + l_f/l_r per platform; out of budget.

### 2026-06-03 — m2-fiala-tire-st (prefilled, scored from scorecard)
- Parent: m1-linear-dynamic-st
- Rung: 2
- Dev pooled: yaw 0.009207, CTE 116.890
- vs V1: yaw +57%, CTE +106%
- Gate: fail (Fiala collapses to linear in low-a_lat regime; inherits m1's unfit-priors failure)
- Residual: structure_detected:inherits-m1-bias
- Verdict: shelve  →  next: only worth re-running once M1 priors are fit.

### 2026-06-03 — m5-friction-circle (prefilled, scored from scorecard)
- Parent: m1-linear-dynamic-st
- Rung: 3
- Dev pooled: yaw 0.009187, CTE 116.890
- vs V1: yaw +57%, CTE +106%
- Gate: fail (friction-circle activates only in high-a_lat coupling; M1 base unfit)
- Residual: structure_detected:inherits-m1-bias
- Verdict: shelve  →  next: blocked on M1.

### 2026-06-03 — m4-relaxation-length (winner)
- Parent: v1
- Rung: orthogonal
- Dev pooled: yaw 0.005634, CTE 52.105 (402 segments, sigma fitted on frozen train split)
- vs V1: yaw +3.8% (slightly worse), CTE -0.2% (slightly better) on this dev split
- Gate: warn (F150 bias_fraction 3.1% — known F150 ceiling; CTE strictly beats V1)
- Residual: noise_floor at Mach-E / Ioniq; structure_detected:F150-load-transfer (heavy-vehicle ceiling)
- Verdict: promote_to_leader (shipped)  →  next: ship as final; F150 yaw ceiling would need M3 double-track to crack.

### 2026-06-03 — m4_plus_ridge_v2 (variant, shelved)
- Parent: m4-relaxation-length
- Rung: orthogonal
- Description: m4 + per-platform 3-feature zero-mean ridge residual (delta-dot, sign(d)*d^2*v, d*v^2).
- Train fit gave 0.5%-2% RMSE improvement per platform.
- Dev pooled: yaw 0.005604, CTE 53.026 — yaw slightly better, CTE 1.8% worse
- Gate: fail (CTE worsened; ridge intercept introduced trajectory drift even with zero-mean features)
- Verdict: shelve  →  next: not worth the complexity; m4 stock dominates on CTE.

### 2026-06-03 — m4_plus_jointfit (variant, shelved)
- Parent: m4-relaxation-length
- Rung: orthogonal
- Description: refit sigma JOINTLY with V1 (g, L_eff, K_us) scales per platform via Nelder-Mead.
- Dev pooled: yaw 0.005639, CTE 53.030 — both worse than stock m4.
- Gate: fail (train-dev gap; F150 specifically overfit — scales drifted by 4-25%)
- Verdict: shelve  →  next: V1 params are already well-tuned; freeing them is overfit.

