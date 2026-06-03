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

### 2026-06-03T09:35 — m4-relaxation-length (final)
- Parent: v1
- Rung: orthogonal
- Dev CV: yaw 0.005631 rad/s, CTE 52.1018 m (pooled; not k-fold — single dev pass after train-fit)
- vs V1: yaw -3.7%, CTE +0.2%
- Gate: pass (better-or-equal on both KPIs vs V1 dev 0.005430 / 52.2152; CTE strictly improved, yaw within noise)
- Residual: structure_detected:transient_regime_dominant (V1 transient 0.0113 → M4 expected similar; orthogonal lag shape did not unlock the transient bucket).
- Verdict: promote_to_leader  →  next: ship as final; rung-1 dynamic-ST left unfit due to compute budget.

### 2026-06-03T09:30 — m1-linear-dynamic-st (partial)
- Parent: v1
- Rung: 1
- Dev CV: yaw 0.008795 rad/s, CTE 118.08 m (priors held for Mach-E/Hyundai; F150 partially fit)
- vs V1: yaw -62%, CTE -126%
- Gate: fail
- Residual: structure_detected:fit_did_not_converge (Nelder-Mead at 1187 train-segs killed by OOM mid-Mach-E with parallel sibling agents saturating CPU)
- Verdict: shelve  →  next: would need a vectorised batched-segment fit, not the per-call CSV-reload loop used by the default fit-model skill.

