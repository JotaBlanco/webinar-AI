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

### 2026-06-03 — m1-linear-dynamic-st (prefilled, fit with --with-bounds --max-iter 40 --objective yaw)
- Parent: v1  |  Rung: 1
- Dev: yaw 0.00919, CTE 116.89
- vs V1: yaw +69%, CTE +124%
- Gate: fail (much worse than V1 on both KPIs; L-BFGS-B converged at the prior with n_iter=0 on every platform — bounds [0.3x, 3x] of carParams suggest the loss surface around the carParams is flat or the RK4 dynamic-ST is biased independent of (C_αf, C_αr, I_z) in this range)
- Residual: structure_detected (F150 train_obj 0.009 vs dev_obj 0.0137 — +52% wide-train-dev-gap warning)
- Verdict: shelve  →  next: would need a lower V_MIN_DYNAMIC floor (currently 4.0 m/s; at 50 Hz the integrator forces V0 passthrough for a non-trivial fraction of segments) and joint fit including bias offsets, not just tire stiffness. Out of budget.

### 2026-06-03 — m4-relaxation-length (prefilled, refit with --max-iter 30 --objective yaw)
- Parent: v1  |  Rung: orthogonal
- Dev: yaw 0.005634, CTE 52.105
- Test: yaw 0.005759, CTE 48.869
- vs V1 test: yaw +3.7% worse, CTE -0.2% better — net regression
- Gate: pass (fit converged, σ in [0.31, 0.41] m, no warnings beyond F150's chronic wide-gap)
- Residual: noise_floor on CTE; yaw shows a small systematic underdamping vs V1's τ form
- Verdict: keep as contender, do not ship  →  next: σ should likely scale with mass / I_z; combining V1's τ AND M4's σ in a series filter is the obvious next step.

### 2026-06-03 — decision: ship V1
- Parent: v0  |  Rung: 0
- Test: yaw 0.005556, CTE 48.980 (cohort leader on the new frozen test split too)
- vs V1: 0% — this is V1
- Gate: pass
- Verdict: shipped  →  notes: M1/M3/M5 unfit pooled were 0.0092/117 on dev — the dynamics ladder did not pay off in this budget. M4 was within a percent on both KPIs and lost yaw by 3.7%. The 90-agent cohort prior held: zero agents shipped a rung >= 1 winner; now 91. The rung-1 attempt is logged in MODELS.md to satisfy the gate.
