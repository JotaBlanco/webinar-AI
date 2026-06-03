# MODELS.md — candidate model registry (tree-structured)

V1's pooled-dev scores (constants — do NOT score V1 again, this is the truth
of record): `yaw_rmse = 0.005874 rad/s`, `cte_rmse = 56.81 m`.
Locally re-scored on this module's frozen split: V1 yaw=0.005430, cte=52.22.

The tree structure these entries form is also persisted in `TREE.json` —
human-readable here, machine-readable there.

---

## v1-baseline-pristine
- dir: final-model/
- parent: v1
- rung: 0
- structure: refines-v1
- status: shipped
- pooled-yaw-rmse-dev: 0.005430
- pooled-cte-rmse-dev: 52.2152
- vs-v1: yaw 0%, CTE 0% (V1 verbatim)
- vs-parent: n/a
- gate: pass
- next: shipped
- notes: V1 verbatim. M1 and M4 climbs attempted and lost on dev yaw RMSE.

## m1-linear-dynamic-st
- dir: phases/3-implement/models/m1-linear-dynamic-st/
- parent: v1
- rung: 1
- structure: differs-from-v1
- status: kept (gate-failed-on-quality)
- pooled-yaw-rmse-dev: 0.008156
- pooled-cte-rmse-dev: 101.292
- vs-v1: yaw +50%, CTE +94% (WORSE than V1)
- vs-parent: yaw +50% worse
- gate: fail (worse-than-V1)
- next: would need full-train Nelder-Mead on `yaw_plus_cte` objective + careful
  C_alpha bounds; budget did not allow. Train-dev gap is large on F150 / Mustang.
- notes: rung-1 attempt (canonical climb requirement). Fit via custom fast
  log-space Nelder-Mead on 30 longest train segments per platform. F150
  fitted C_alpha_f=196k vs prior 378k — collapsed toward Ioniq scale,
  suggesting the optimiser found a local min that doesn't generalise.

## m2-fiala-tire-st
- dir: phases/3-implement/models/m2-fiala-tire-st/
- parent: m1-linear-dynamic-st
- rung: 2
- structure: differs-from-v1
- status: drafting
- pooled-yaw-rmse-dev: 0.00921 (priors, no fit — budget exhausted)
- pooled-cte-rmse-dev: 116.89 (priors, no fit)
- vs-v1: not assessed
- vs-parent: drafting
- gate: pending
- next: would inherit M1's fitted C_alpha; only meaningful in high-a_lat regime.
- notes: not attempted in this run — M1 underperformed V1 so the rung-2
  refinement is moot until rung-1 holds.

## m3-double-track-load-transfer
- dir: phases/3-implement/models/m3-double-track-load-transfer/
- parent: m2-fiala-tire-st
- rung: 3
- structure: differs-from-v1
- status: drafting
- pooled-yaw-rmse-dev: 0.00921 (priors, no fit)
- pooled-cte-rmse-dev: 116.89 (priors, no fit)
- vs-v1: not assessed
- vs-parent: drafting
- gate: pending
- next: would target the F150 ceiling specifically. Not reached in budget.
- notes: not attempted in this run.

## m4-relaxation-length
- dir: phases/3-implement/models/m4-relaxation-length/
- parent: v1
- rung: orthogonal
- structure: differs-from-v1
- status: kept (lost-by-margin)
- pooled-yaw-rmse-dev: 0.005631
- pooled-cte-rmse-dev: 52.1018
- vs-v1: yaw +3.7%, CTE -0.2% (essentially tied on CTE, slightly worse yaw)
- vs-parent: same direction as V1
- gate: warn (tied)
- next: try yaw_plus_cte objective; might pick a sigma that wins CTE without
  the yaw penalty.
- notes: σ swept per-platform on train: F150 0.40, Mustang 0.40, Ioniq 0.30.
  Distance-domain lag re-parameterises V1's time lag; near-tie confirms the
  τ ≈ σ/v equivalence at typical v.

## m5-friction-circle
- dir: phases/3-implement/models/m5-friction-circle/
- parent: m1-linear-dynamic-st
- rung: 3
- structure: differs-from-v1
- status: drafting
- pooled-yaw-rmse-dev: 0.00919 (priors, no fit)
- pooled-cte-rmse-dev: 116.89 (priors, no fit)
- vs-v1: not assessed
- vs-parent: drafting
- gate: pending
- next: would help only on brake/accel events. Not reached in budget.
- notes: not attempted.
