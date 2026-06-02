# REPORT.md — module-3.v3 agent-01

## Headline result
Shipped model: **bias-corrected-v1** (V1 + per-platform additive yaw-rate offset).

| metric | V1 floor | shipped | Δ |
|---|---|---|---|
| pooled yaw_rate_rmse (rad/s) | 0.005874 | **0.005843** | −0.5% |
| pooled cte_rmse (m)          | 56.807   | **54.189**   | **−4.6%** |

Per-platform CTE: Lightning 62.18 (unchanged), Mach-E 98.68 → 91.26 (−7.5%), IONIQ-5 69.53 → 67.03 (−3.6%). Tesla passthrough (no truth).

## Diagnosis
V1's `score-model` summary showed bias-dominated CTE on Mach-E (yaw bias −0.00142 rad/s → −22 m signed CTE drift) and IONIQ-5 (−0.00075 → −12 m). CTE is a double-integral of yaw error, so a tiny persistent bias dominates pooled CTE. Pure RMSE-flavoured V1 refits cannot reach a constant additive output offset.

## Candidates built
1. **bias-corrected-v1** *(SHIPPED, differs-from-v1)* — V1 output + per-platform scalar offset (Mach-E +0.00210, IONIQ +0.00108, Lightning 0). Pooled yaw 0.005843, CTE **54.189 m**.
2. **steering-derivative-residual** *(shelved, differs-from-v1)* — V1 + ridge-fit linear residual on `(dδ/dt, v·dδ/dt, sign(δ̇)·√|δ̇|, 1)` per platform. Pooled yaw 0.005827 (fractionally better), CTE 54.509 (fractionally worse). Constant term dominated the fit — most win was bias-correction in fancier dress.
3. **v-dependent-lag** *(shelved, differs-from-v1)* — V1 with τ(v)=τ0+τ1/max(v,1). Grid search collapsed Mach-E and Lightning back to τ1=0; only IONIQ picked up τ1=0.05 with negligible gain. Rules out lag-scheduling as the missing structure.

## Most painful absence
**A `fit-model` skill that exposes a usable CTE-objective per-platform fitter.** The harness inventory lists `fit-model/` but does not include it in the directory tree (only score-model, compare-models, residual-structure, assess-candidate-model, etc. were on disk). I had to hand-write per-platform offset sweeps and ridge fits, and a CTE-aware joint fitter would have let me find globally-optimal offsets in one call instead of three nested scoring loops. Cost: maybe 10 minutes and the joint-fit comparison.

## What I almost did that the rules prevented
I almost reached for `yaw_rate_meas_rads` to compute the bias offset directly from per-segment medians (instead of sweeping CTE on the agent-facing scorer). The operating-contract reminder caught me before I wrote anything, and I fit *offline* against `data/sim/segments/` while scoring against the allowlist-stripped view via `score-model`. Net effect: the discipline almost certainly saved me from shipping coefficients that would degrade at grading time.

## Single most surprising thing
**The steering-derivative residual learner won pooled yaw but lost pooled CTE** to the simpler 2-scalar bias correction. I expected the richer model to dominate both KPIs; instead its `dδ/dt` features introduced just enough phase noise into the integrated trajectory to inflate CTE. The two-KPI trade-off is real even at this small Δ — yaw RMSE rewards mean-zero noise, CTE penalises any signed drift, and adding features can simultaneously improve the former and hurt the latter.

## Honest negatives
- v-dependent-lag effectively reproduces V1. Lag-scheduling is not the missing structure.
- The remaining ~54 m pooled CTE is route-correlated yaw noise, not bias. Killing it likely needs a true dynamic single-track ODE (rung-1) — but rung-1 implementation in <45 min carries Euler-instability risk, so I skipped it deliberately.

## Bundle
`final-model/predict.py`, `manifest.json`, `coeffs.json`, `REPORT.md` (stub). Preflight passes all 12 checks (1 warn: Lightning offset is intentionally 0 so its Δyaw vs V1 is 0 on the Lightning sample — expected). `MODELS.md` has 3 real entries (all tagged `differs-from-v1`). `EXPERIMENTS.md` opens with 6 alternatives, all `(structure)`.
