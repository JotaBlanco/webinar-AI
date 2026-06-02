# Module 4 v2 — agent-09 — idea-01 lateral fidelity

## Headline

Macro-mean across the four platforms vs V0 (kinematic single-track, pre-computed
`yaw_rate_pred_rads`), evaluated on the full `data/sim/segments/` set with the
provided `_shared/traj_metrics.cte_rmse_segment` definition:

| metric                    |    V0     |  Final   |   delta   |
|---------------------------|-----------|----------|-----------|
| yaw RMSE [rad/s]          | 0.01387   | 0.00947  | **-31.7%** |
| distance-resampled CTE [m]| 139.07    |  73.32   | **-47.3%** |

Per-platform:

| platform                  | n_seg | yaw V0 -> Final          | CTE V0 -> Final               |
|---------------------------|------:|--------------------------|-------------------------------|
| TESLA_MODEL_3             |  781  | 0.00201 -> 0.00201 (-0.1%) | 3.26 m -> 3.26 m (+0.0%)    |
| FORD_MUSTANG_MACH_E_MK1   |  240  | 0.01650 -> 0.01379 (-16.4%)| 148.00 m -> 122.31 m (-17.4%) |
| FORD_F_150_LIGHTNING_MK1  |  175  | 0.01941 -> 0.01268 (-34.7%)| 157.51 m -> 60.99 m  (-61.3%) |
| HYUNDAI_IONIQ_5           |  800  | 0.01755 -> 0.00940 (-46.4%)| 247.50 m -> 106.72 m (-56.9%) |

## What I shipped

`final-model/predict.py` — single closed-form predictor, per-platform coefficients
in `final-model/coeffs.json`. Model is:

    delta_eff[k] = (delta_road_rad[k] + delta_offset) * scale
    yr_ss[k]     = v[k] * delta_eff[k] / (L + K_us * v[k]^2)         # steady-state understeer
    yr[k+1]      = yr[k] + dt[k] * (yr_ss[k] - yr[k]) / tau           # first-order yaw lag
    x, y         = Euler integration matching traj_metrics convention

Per-platform fitted parameters (Nelder-Mead on pooled yaw RMSE):

| platform                | K_us      | scale | delta_offset | tau  |
|-------------------------|-----------|-------|--------------|------|
| TESLA_MODEL_3           | 0         | 1.00  | 0            | 0    |
| FORD_MUSTANG_MACH_E_MK1 | 2.61e-3   | 1.181 | +0.04 mrad   | 0.069 s |
| FORD_F_150_LIGHTNING_MK1| 3.51e-3   | 0.959 | -1.23 mrad   | 0.058 s |
| HYUNDAI_IONIQ_5         | 3.39e-3   | 0.970 | +0.52 mrad   | 0.051 s |

Tesla degrades to V0 because the Tesla `sim.csv` training schema has
`psi_dot_rads` (the KS simulator state output) as the only available yaw-rate
column — verified to be `v * delta_road / L` to within 4e-4 rad/s, i.e. the
truth IS KS-clean by construction, so V0 is already optimal for that platform.

## Variants tried

1. **V0 baseline** (passthrough of `yaw_rate_pred_rads`). Numbers above.
2. **Understeer steady-state** `yr = v*delta*scale / (L + K_us*v^2)`. Already
   gives most of the win on yaw RMSE; CTE worsens slightly on Tesla (expected),
   reduces 17-55% on the others.
3. **Understeer + per-platform delta_offset.** Only changes the F-150 (-1.2 mrad
   trim) materially; on that one platform it halves CTE from ~108 m to ~61 m.
4. **+ first-order yaw lag tau.** Yaw RMSE drops another 1-3%, CTE unchanged
   (lag is symmetric, doesn't introduce bias). Kept because it's free at predict
   time and never hurts.

A linear dynamic bicycle (in `_shared/rung1_starter.py`) was available but the
understeer-bicycle steady-state plus lag captures almost all of the gain at a
fraction of the complexity, and never destabilises. Did not pursue further.

## Most painful absence in the harness

A **per-segment offset estimator**. Per-segment yaw bias has std ~5 mrad/s and
dominates the residual CTE — but at grading time the contract gives me 8
input-only columns, no measured yaw, so I cannot remove it. A harness component
that surfaced "what fraction of remaining CTE is per-segment bias I could remove
if I had K seconds of warm-up truth" would have ended the iteration loop a step
earlier. The closest existing piece is `_shared/traj_metrics.cte_diagnostics_segment`
(returns `sum_signed_m`), which gave me the smell but not the decomposition.

The `skills/critique-residuals` directory referenced in the brief is listed but
I never opened it (out of time budget); a *typed* residual structure router
would likely have routed me toward "lateral acceleration bias vs steering offset
bias" earlier than the manual numpy I wrote.

## Rules-prevented drift

When I noticed Tesla's "truth" (`psi_dot_rads`) was suspiciously close to KS, my
first instinct was to grep across `module-4.v1`/`module-3.v3` to see whether
other cohort agents had hit the same surprise — those paths are on the
forbidden list. Instead I confirmed it locally with `np.corrcoef` and a
mean-abs-diff (correlation 0.99997, mean diff 3.9e-4 rad/s), which is faster
anyway. The block forced a cleaner diagnostic.

## Most surprising thing learned

The headline V0 yaw RMSE on the Tesla split (~2 mrad/s) isn't model skill — it's
**dataset construction skill**. Tesla's `sim.csv` truth column is the KS
simulator's own state output. Any "improvement" on Tesla is fighting numerical
noise in the data generation pipeline, not the model. Across cohorts, anyone
reporting a Tesla yaw-RMSE win without checking the truth/V0 correlation is
likely measuring optimisation overfit. The right move on Tesla is "predict V0,
declare optimality, move on."
