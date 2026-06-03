# MODELS.md — candidate model registry (tree-structured)

One `##`-level entry per candidate. **Do not edit by hand** — the `iterate`
skill appends entries as you score candidates with it. Hand-edits are allowed
for the `verdict` and `notes` fields once a candidate is assessed, but the
machine fields (scores, gate, parent linkage) are owned by `iterate`.

Preflight enforces:
- ≥4 entries total
- ≥1 entry tagged `rung: 1` or `rung: 2` or `rung: orthogonal`
- ≥1 entry with `gate: pass`
- The shipped candidate's `parent` chain must reach `v1` without loops

Schema (every field is populated by `iterate`):

```
## <model-name>
- dir: models/<model-name>/
- parent: <model-name-or-"v1">
- rung: 0 | 1 | 2 | 3 | orthogonal
- structure: refines-v1 | differs-from-v1
- status: drafting | gate-failed | kept | shelved | promote_to_leader | shipped
- pooled-yaw-rmse-dev: <number ± std>
- pooled-cte-rmse-dev: <number ± std>
- vs-v1: yaw +N%, CTE +N%
- vs-parent: yaw +N%, CTE +N%
- gate: pass | warn (reasons) | fail (reasons) | pending  (`pending` = seed-only placeholder for v2.01's prefilled candidates; does NOT satisfy the preflight `≥1 entry with gate: pass` requirement)
- next: <routing string from critique-residuals>
- notes: <one-line agent annotation, optional>
```

`structure:` is derived from `rung:` — anything with `rung: 0` whose parent
is also `rung: 0` is `refines-v1`; everything else is `differs-from-v1`.

V1's pooled-dev scores (constants — do NOT score V1 again, this is the truth
of record): `yaw_rmse = 0.005874 rad/s`, `cte_rmse = 56.81 m`.

The tree structure these entries form is also persisted in `TREE.json` —
human-readable here, machine-readable there. Use `skills/visualise-tree/` to
render either as ASCII or markdown.

---

<!-- v2.01 prefilled candidates below — status: drafting until you fit them -->

## m1-linear-dynamic-st
- dir: phases/3-implement/models/m1-linear-dynamic-st/
- parent: v1
- rung: 1
- structure: differs-from-v1
- status: drafting
- pooled-yaw-rmse-dev: 0.00919 (priors, no fit)
- pooled-cte-rmse-dev: 116.89 (priors, no fit)
- vs-v1: yaw -56%, CTE -106% (UNFIT — fit before judging)
- vs-parent: n/a (root of dynamics branch)
- gate: pending
- next: run `python fit.py && python eval.py` from the model dir, then `skills/iterate models/m1-linear-dynamic-st`
- notes: canonical rung-1 climb. Two-state ODE [β, ψ̇], RK4.

## m2-fiala-tire-st
- dir: phases/3-implement/models/m2-fiala-tire-st/
- parent: m1-linear-dynamic-st
- rung: 2
- structure: differs-from-v1
- status: drafting
- pooled-yaw-rmse-dev: 0.00921 (priors, no fit)
- pooled-cte-rmse-dev: 116.89 (priors, no fit)
- vs-v1: yaw -57%, CTE -106% (UNFIT)
- vs-parent: ~tied at priors (Fiala collapses to linear in small-angle regime)
- gate: pending
- next: run `python fit.py && python eval.py`, then iterate
- notes: nonlinear (Fiala) tire on top of M1. Targets high-`a_lat` saturation.

## m3-double-track-load-transfer
- dir: phases/3-implement/models/m3-double-track-load-transfer/
- parent: m2-fiala-tire-st
- rung: 3
- structure: differs-from-v1
- status: drafting
- pooled-yaw-rmse-dev: 0.00921 (priors, no fit)
- pooled-cte-rmse-dev: 116.89 (priors, no fit)
- vs-v1: yaw -57%, CTE -106% (UNFIT)
- vs-parent: ~tied at priors (load transfer needs high a_lat to show)
- gate: pending
- next: run `python fit.py && python eval.py`, then iterate; check F150 specifically.
- notes: targets the F150 ceiling (see references/f150-yaw-ceiling.md).

## m4-relaxation-length
- dir: phases/3-implement/models/m4-relaxation-length/
- parent: v1
- rung: orthogonal
- structure: differs-from-v1
- status: drafting
- pooled-yaw-rmse-dev: 0.00585 (default σ=0.5)
- pooled-cte-rmse-dev: 52.13 (default σ=0.5)
- vs-v1: yaw +0.4%, CTE +8% (near-tie at default σ; **fit σ** for real comparison)
- vs-parent: n/a
- gate: pending
- next: run `python fit.py && python eval.py`. σ may collapse to 0 (null result) or land between 0.3–1.2 m.
- notes: distance-domain phase-lag formulation. Orthogonal to dynamics ladder.

## m5-friction-circle
- dir: phases/3-implement/models/m5-friction-circle/
- parent: m1-linear-dynamic-st
- rung: 3
- structure: differs-from-v1
- status: drafting
- pooled-yaw-rmse-dev: 0.00919 (priors, no fit)
- pooled-cte-rmse-dev: 116.89 (priors, no fit)
- vs-v1: yaw -56%, CTE -106% (UNFIT)
- vs-parent: ~tied at priors (friction-circle only active in long-lat events)
- gate: pending
- next: run `python fit.py && python eval.py`. Helps most on brake/accel segments.
- notes: long-lat coupling via friction circle. Reads `a_long_mps2` + `brake_pressed`.

<!-- iterate-skill appends new candidate entries below this line -->

## m4-relax-yawfit
- dir: phases/3-implement/models/m4-relaxation-length/
- parent: m4-relaxation-length
- rung: orthogonal
- structure: differs-from-v1
- status: shipped
- pooled-yaw-rmse-dev: 0.005634
- pooled-cte-rmse-dev: 52.1053
- vs-v1: yaw +4.1%, CTE +8.3%
- vs-parent: yaw +3.8%, CTE +0.0% (vs σ=0.5 default)
- gate: pass
- next: shipped to final-model/. F150 warns wide_train_dev_gap (+62%) — load-transfer (M3) likely needed for the ceiling.
- notes: fitted σ per platform via skills/fit-model --objective yaw. F150 σ=0.398, Mach-E σ=0.409, Ioniq σ=0.306. M1 (rung 1) fit attempted but did not complete in budget (ODE/RK4 too slow on pooled segments at this iter count).

<!-- m1-linear-dynamic-st climb attempt: priors-only scorecard above; live fit shelved due to RK4 ODE wall-time at 402-segment scale within budget. -->


