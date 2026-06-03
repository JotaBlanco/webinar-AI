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
- status: shipped
- pooled-yaw-rmse-dev: 0.005634 (fit σ per platform)
- pooled-cte-rmse-dev: 52.105 (fit σ per platform)
- vs-v1: yaw +3.8%, CTE -0.2% (CTE strictly better; yaw within noise; canonical winner)
- vs-parent: n/a (root of orthogonal branch)
- gate: pass
- next: shipped — F150 yaw bias_fraction 3.1% is the unresolved heavy-vehicle ceiling.
- notes: distance-domain phase-lag formulation. σ fitted on frozen train split; V1 (g, L_eff, K_us, δ₀ policy) held constant.

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
