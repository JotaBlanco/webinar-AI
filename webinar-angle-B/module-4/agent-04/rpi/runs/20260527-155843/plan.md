# Plan — 20260527-155843 (LOCKED)

## Variant ladder

| # | Variant | Physical hypothesis | DoF added | Predicted direction | Falsifiable success criterion |
|---|---------|---------------------|-----------|---------------------|-------------------------------|
| V0 | baseline (`yaw_rate_resid_rads` as-is) | none | 0 | — | reference |
| V1 | **Per-segment yaw-rate bias removal** | IMU yaw-gyro has a slowly-varying per-segment DC offset; subtracting `mean(resid)` per segment removes it. Estimated globally (not LOSO) because it is a sensor-trait correction, not a model parameter. | +1 / segment | Straight RMSE drops materially (>20%); cornering RMSE drops modestly. | If `straight` RMSE does not drop by ≥20%, the bias was not the dominant straight-line failure mode. |
| V2 | **Linear ST steady-state gain, prior C_α** | Replace KS `ψ̇ = v·tan(δ)/L` with ST steady-state `ψ̇ = v·δ / (L·(1 + K_us·v²))` using `PARAM_BY_PLATFORM` priors. Speed-known, applied on top of V1. Fallback to KS for v<2 m/s. | +1 (understeer gradient) | Steady cornering RMSE drops; straight ≈ unchanged. | If `steady` RMSE does not drop, prior `C_α` does not match these tyres or transient dynamics dominate even in `steady`. |
| V3 | **Fit C_α (jointly) to data** | Refit `C_αf, C_αr` by least-squares against `yaw_rate_meas_rads` on cornering samples, bounded 50–500 kN/rad. Same ST functional form as V2. | +2 | Steady RMSE drops further; overall drops. | If best-fit pegs at the 500 kN/rad bound, linear ST is the wrong form, not the priors. Flag as regression. |
| V4 | **First-order yaw-rate lag** | Add a single-time-constant low-pass `τ·ψ̇' + ψ̇ = ψ̇_ST` with `τ` fit globally to data. Targets the transient regime which steady-state ST cannot capture. | +1 (τ) | Transient RMSE drops; steady ≈ unchanged. | If transient RMSE does not drop or `τ` fits at the boundary (<0.02 or >1 s), the lag model is wrong (resonance, not first-order). |

## Attribution scheme

**Strict marginal in fixed order V0→V4.** Each row's "Marginal drop" column = RMSE(prev) − RMSE(this) on overall sample. Marginal drops sum to total V0 → V4 by construction. We additionally check sum-of-per-regime-N-weighted drops ≈ overall drop within 15%.

## Regime mask (fixed, applied identically to every variant)

- **Straight**: `|delta_road_rad| < 0.01 rad`
- **Steady cornering**: `|delta_road_rad| ≥ 0.01 ∧ |dδ/dt| < 0.05 rad/s` (dδ/dt by per-segment diff at 50 Hz)
- **Transient cornering**: `|delta_road_rad| ≥ 0.01 ∧ |dδ/dt| ≥ 0.05 rad/s`

Same Mach-E sample set (913,626 samples, 315 segments) across every variant.

## What would invalidate this plan

- If V1 (segment-bias) does not drop straight RMSE materially, the straight residual is structural (e.g. timing / resampling artefact) and V2-V4 will be optimising the wrong thing. Ship partial.
- If V2-V3 increase RMSE in any regime, report as regression with physical reason; do not silently drop the rung.

## Locked at: 2026-05-27 15:58 UTC
