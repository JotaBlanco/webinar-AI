# Phase 2 — Locked plan

## Platform
**FORD_MUSTANG_MACH_E_MK1.** Larger n (~914k), cleaner straight-line bias, smaller absolute baseline RMSE — gives best signal-to-noise for variant attribution. Lightning carries a steering-offset confound that would muddy V1 attribution.

## Variant ladder
- **V0** — baseline KS as-shipped (read `yaw_rate_resid_rads` from sim.csv directly). No re-run.
- **V1** — KS recalibration: refit per-platform understeer gradient `(lf+lr)/L` style tweak — adjust `wheelbase` and steer ratio implicit in `delta_road_rad` is already applied; here recalibrate the linear-bicycle gain `yr = v*delta/L` by least-squares-fitting an effective `L_eff` on straight + steady samples, then recompute prediction.
- **V2** — Linear single-track **prior**: use canonical CommonRoad linear-ST closed-form yaw-rate with stock parameters (Cf, Cr, m, Iz, lf, lr from `parameters.py`). No fitting. Tests whether ST structure alone helps over KS.
- **V3** — Linear single-track **fit**: same model as V2 but cornering stiffnesses `Cf, Cr` (and optional `L_eff`) least-squares-fitted to measured yaw-rate over the train pool; report on the same pool (in-sample — flag).

## Attribution
Marginal-RMSE accounting, **variant-minus-prior** (skill convention): `delta_i = RMSE_{i-1} - RMSE_i`. Per-regime breakdown via `regime-comparison` skill. Regression flag if any regime RMSE rises by >5% relative.

## Reporting shape (REPORT.md sections)
1. Platform & contract
2. Variant table (V0..V3 with overall RMSE + marginal delta)
3. Per-regime attribution (regime-comparison output)
4. Regression flags
5. Phase-surfacing notes (which phase surfaced which decision)
6. Plan dissent (if any)

## Explicitly out of scope
- **V4 residual learner** (e.g., gradient-boost on speed/steer/yaw): rejected — opaque, no causal attribution, undermines marginal-RMSE accounting.
- **Bicycle dynamic model with tire saturation**: rejected — transient n too small to fit nonlinear tire curves reliably.
- **Lightning platform**: rejected — confounded steering offset; can revisit in a follow-up.
- **Sequence/Kalman smoothing of measured yr**: rejected — modifies the truth channel.
