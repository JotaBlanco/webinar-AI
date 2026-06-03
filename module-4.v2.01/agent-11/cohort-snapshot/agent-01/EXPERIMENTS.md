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

### 2026-06-03 — m1-linear-dynamic-st (hand entry, iterate not run)
- Parent: v1
- Rung: 1
- Dev: yaw 0.008156, CTE 101.292 (pooled, n=402)
- vs V1: yaw +50.2%, CTE +93.9% (V1 dev = 0.005430 / 52.22 on this module's split)
- Gate: fail (worse-than-V1 on both KPIs)
- Residual: structure_detected:wide_train_dev_gap_F150 (train 0.0059, dev 0.0104 for F150).
- Verdict: shelve  →  next: full-train Nelder-Mead with yaw_plus_cte and tighter C_alpha bounds; budget did not allow.
- Method: fast log-space Nelder-Mead on 30 longest train segments per platform (CPU contended by parallel agents — see absence note in REPORT.md).
- Coeffs landed: F150 C_alpha_f=196377 C_alpha_r=256755 I_z=9646; Mustang C_alpha_f=236820 C_alpha_r=191531 I_z=12933; Ioniq C_alpha_f=142122 C_alpha_r=569391 I_z=7280.
- Observation: optimizer collapsed F150 C_alpha toward Ioniq scale — likely local min on sub-sampled train.

### 2026-06-03 — m4-relaxation-length (hand entry, iterate not run)
- Parent: v1
- Rung: orthogonal
- Dev: yaw 0.005631, CTE 52.1018 (pooled, n=402)
- vs V1: yaw +3.7%, CTE -0.2% (essentially tied on CTE, slightly worse yaw)
- Gate: warn (tied)
- Residual: noise_floor (relative to V1 — σ re-parameterises V1's τ lag)
- Verdict: keep  →  next: try yaw_plus_cte objective.
- Method: per-platform σ sweep on train over {0, 0.25, ..., 5.0} m with refinement near the minimum; best σ = 0.40 (F150), 0.40 (Mustang), 0.30 (Ioniq).
- Observation: confirms V1 τ ≈ σ/v equivalence at typical highway v; the orthogonal axis didn't unlock anything yaw-side, though CTE rounded slightly favorable.

### 2026-06-03 — v1-baseline-pristine (shipped)
- Parent: v1
- Rung: 0
- Dev: yaw 0.005430, CTE 52.2152 (pooled, n=402)
- vs V1: 0% / 0% (verbatim)
- Gate: pass
- Verdict: shipped as final-model.
- Rationale: M1 (rung-1) and M4 (orthogonal) both attempted and lost to V1 on pooled-dev yaw RMSE within the budget. Consistent with the 90-agent cohort prior: V1 is the ceiling for the kinematic + understeer family on this dataset under available compute.
