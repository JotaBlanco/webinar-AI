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

### 2026-06-02 — V0 (passthrough)
- Parent: — | Rung: 0
- Local pooled: yaw 0.017632, CTE 218.16 m
- Reference floor (V0 yaw_rate_pred_rads).

### 2026-06-02 — V1 (kinematic single-track + understeer + lag + per-seg δ₀)
- Parent: V0 | Rung: 0
- Local pooled: yaw 0.010612, CTE 75.6453 m
- Stock from code/v1_baseline.py. Constants on this dataset; per-platform
  yaw RMSE F-150 0.012733 / Mach-E 0.013633 / Hyundai 0.008933.

### 2026-06-02 — V2a (V1 + per-seg straight-driving yaw bias + gain)
- Parent: V1 | Rung: orthogonal (data-driven post-hoc)
- Decision: discarded. Per-seg bias removal collided with per-seg δ₀ that V1
  already does, and on F-150 (constant δ₀) the bias estimator picked up
  legitimate yaw during gentle turns. CTE blew up to 111 on F-150.

### 2026-06-02 — V2b (V1 + per-seg δ₀ also on F-150 + gain/offset)
- Parent: V1 | Rung: 0
- Pooled: yaw 0.010661, CTE 81.04 m. Rejected.
- F-150 yaw barely moves but its CTE doubles (62→112). The F-150 segment
  population has long, straight-driving spans where the median δ_road in
  V1's mask captures structural toe offset that becomes a systematic CTE
  drift once integrated.

### 2026-06-02 — V2c (V1 + per-platform OLS gain g, offset c) — SHIPPED
- Parent: V1 | Rung: orthogonal (data-driven calibration head)
- Fit: OLS on yaw_truth = g · yr_v1 + c per platform, hash-mod-5 split.
- Coeffs: F-150 g=0.986 c=-0.000296; Mach-E g=0.978 c=+0.001674;
  Hyundai g=0.990 c=+0.000591; Tesla 1.0/0.0.
- Pooled: yaw 0.010527, CTE 72.59 m.
- Gate: pass — every per-platform yaw and CTE improves vs V1.

### 2026-06-02 — V2d (V2c + conservative per-seg straight-line bias)
- Parent: V2c | Rung: orthogonal
- Pooled: yaw 0.010538, CTE 73.50 m. Marginal regression vs V2c; rejected.
