# Agent-05 — Lateral Fidelity, Module 2

## Approach

Two layers of correction over the V0 kinematic single-track model, both speed-known and per-platform:

1. **Understeer-corrected linear bicycle** (steady-state form):
   `yr = g · v · (δ − δ₀) / (L + K_us · v²)`
   - `g` corrects the steering-ratio scale that openpilot's `carParams.steerRatio` misses (notably ~19 % under-reporting on the Mach-E).
   - `K_us` injects the speed-dependent understeer the pure kinematic model ignores.
   - `δ₀` absorbs a small static toe/alignment offset (~1 mrad on the F-150 Lightning).
2. **First-order steering+tire lag** with per-platform time constant τ (~55 ms), applied as a dt-aware causal LPF on the bicycle yaw rate. This captures the lumped actuator and sidewall compliance the kinematic model doesn't have. Biggest win is in the transient regime.

Parameters were fitted by Nelder-Mead on a 75/25 whole-route, platform-stratified split (seed 42) using sample-pooled MSE on yaw-rate, masked to `v_mps > 2`.

Coefficients (final, in `coeffs.json`):

| Platform | L (m) | g | K_us | δ₀ (rad) | τ (s) |
|---|---|---|---|---|---|
| FORD_MUSTANG_MACH_E_MK1 | 2.984 | 1.2124 | 0.00302 | −0.00018 | 0.0585 |
| FORD_F_150_LIGHTNING_MK1 | 3.700 | 0.9784 | 0.00395 | 0.00134 | 0.0525 |
| TESLA_MODEL_3 (untrained fallback) | 2.875 | 1.000 | 0.00300 | 0.00000 | 0.0500 |

## Results

Whole-route, platform-stratified split (seed=42). Dev = 108 of 415 segments (truly held out).

| Model | DEV yr-RMSE | DEV CTE-RMSE | TRAIN yr-RMSE | TRAIN CTE-RMSE |
|---|---|---|---|---|
| V0 baseline | 0.01308 | 129.06 | 0.01536 | 158.31 |
| V1 (bicycle, no lag) | 0.00890 | 91.87 | 0.00823 | 104.15 |
| **V2 (bicycle + lag, shipped)** | **0.00851** | **92.32** | **0.00755** | **104.25** |

Per-platform DEV (V0 → V2):
- FORD_F_150_LIGHTNING_MK1: yr 0.0125 → 0.0052; CTE 127.4 → 63.8
- FORD_MUSTANG_MACH_E_MK1: yr 0.0136 → 0.0105; CTE 130.7 → 113.5

Per-regime DEV yr-RMSE (V0 → V2): straight 0.0086 → 0.0066; steady 0.0250 → 0.0137; transient 0.0360 → 0.0219.

## What I didn't ship

- Full dynamic (ST/linear-bicycle) state-space with side-slip — overkill for the data; calibrated linear bicycle hits diminishing returns and would risk instability without speed-conditioned damping.
- Mach-E gap (CTE still 113 m) likely comes from non-linear steering-ratio variation with steering angle. A second-order polynomial in δ for g(δ) or a small lookup table could close it; ran out of budget.
- No bank-angle or road-grade correction — `a_lat_meas_mps2` would be a hint but isn't in the truth channel set.

## Files

- `predict.py` — exposes `predict(sim_df, platform) -> DataFrame` with `yaw_rate_pred_rads`, `x_m`, `y_m`.
- `coeffs.json` — per-platform calibrated (L, g, K_us, δ₀, τ).
- `manifest.json` — `platform_support`, `predict_callable = "predict.py:predict"`.

Preflight: all checks pass (sample segment round-trips clean).
