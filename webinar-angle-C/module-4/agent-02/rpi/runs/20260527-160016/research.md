# Research — lateral-fidelity challenge

## Operating contract
- KS model in **speed-known, lateral-only** mode: `v` and `δ` clamped to measured every step.
- Predicted lateral states only: `ψ̇_pred = v · tan(δ_road) / L` (kinematic relation).
- Residual convention: `pred − meas` (locked by ratchet #1).
- ISO 8855 left-positive (ratchet #2).
- `delta_road_rad` is the KS input (ratchet #3); `delta_wheel_deg` is upstream.
- Truth only on Ford (ratchet #4). Picked **FORD_MUSTANG_MACH_E_MK1** for more samples (913k vs 667k) and lower V0 (0.01613 vs 0.02037).

## V0 baseline (from `evals/baseline_rmse.py`)
| platform | overall | straight | steady | transient |
|---|---|---|---|---|
| FORD_MUSTANG_MACH_E_MK1 | 0.01613 | 0.00877 | 0.03173 | 0.05680 |
| FORD_F_150_LIGHTNING_MK1 | 0.02037 | 0.00899 | 0.03617 | 0.05190 |

## Plausible failure modes
1. **Constant yaw-rate sensor bias / measurement offset** — would show up as a non-zero median residual in the straight regime (small δ → ψ̇_pred ≈ 0).
2. **Steering reporting lag** — δ as captured by openpilot is downstream of an actuator; ψ̇_meas is from the IMU. A small lag (~40–120 ms) would explode the transient regime far more than steady.
3. **Effective wheelbase / steer-ratio mismatch** — `L=2.984` is canonical, but tire scrub and compliance steer effectively reduce road-wheel angle. Should show as a steady-regime gain error proportional to δ.
4. **Small-angle vs `tan` regime** — tan(δ) ≈ δ to <1% for |δ|<0.17 rad. Unlikely to matter at typical highway δ.

## Skill landscape
- `baseline-residual` — gives V0; matched the eval script. Loaded.
- `ablation-study` — gives the discipline rails. Loaded; will implement loop in `tools/` for tighter control over per-platform fits and to avoid relying on the reference runner's all-platform glob.

## Truth-channel statement
`yaw_rate_meas_rads` is the openpilot CAN IMU yaw-rate channel; available on Ford only. We score against it.

## What's not under test
Longitudinal channel; Tesla; `a_y_pred` is recomputed from ψ̇ per ratchet #9.
