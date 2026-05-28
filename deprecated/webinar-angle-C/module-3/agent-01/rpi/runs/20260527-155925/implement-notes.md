# Implement notes

Ran `tools/lateral_ladder.py` once, both Ford platforms. No deviations from locked plan.

## Test-set RMSE (rad/s), interleaved every-5th split (TEST = idx%5==0)

| variant | platform | overall | straight | steady | transient |
|---|---|---|---|---|---|
| V0 | Mach-E   | 0.01613 | 0.00878 | 0.03147 | 0.05743 |
| V1 | Mach-E   | 0.01616 | 0.00875 | 0.03159 | 0.05754 |
| V2 | Mach-E   | 0.01568 | 0.00977 | 0.02979 | 0.05029 |
| V0 | F-150    | 0.02037 | 0.00899 | 0.03629 | 0.05161 |
| V1 | F-150    | 0.02007 | 0.00800 | 0.03636 | 0.05162 |
| V2 | F-150    | 0.01636 | 0.00636 | 0.02869 | 0.04478 |

V0 test-set overall matches `evals/baseline_rmse.py` overall to 4 decimal places (it computes over the entire frame; test ≈ identical because residuals are stationary across the 5-stride mask).

## Fit values (per-platform)
- Mach-E: bias `b = +0.00110 rad/s`, gain `g = 1.0948`
- F-150 : bias `b = +0.00461 rad/s`, gain `g = 0.8669`

## Attribution (incremental, ΔoverallRMSE on TEST)
- Mach-E: V1 → −0.00002 (no-op), V2 → +0.00045, total +0.00045 (2.8% rel)
- F-150 : V1 → +0.00030,        V2 → +0.00371, total +0.00401 (19.7% rel)

## Regression flags (rule)
- **Mach-E straight regime regresses** under V2 (0.00878 → 0.00977 rad/s). Physical cause: applying a multiplicative gain `g > 1` amplifies the residual yaw-rate signal in straights as well, where the true gain is irrelevant (ψ̇_pred ≈ 0 anyway, so amplification of pred amplifies its own noise / small offset). A two-mode (straight vs cornering) gain would avoid this, but it's outside the locked ladder.
- **a_y_pred (Mach-E) regresses** slightly (0.338 → 0.373). Coupling rule 9 was honoured (`a_y = v · ψ̇_corrected`), but lateral-G truth `a_lat_meas_mps2` evidently carries calibration that does not match `v · ψ̇_meas` — a separate residual that the yaw-rate-only ladder does not address. F-150 a_y is dominated by sensor-scale issues (RMSE ~10 m/s² indicates the column is mostly the gravity component / channel mis-scaled — flagged but not in scope).

## Falsifier outcomes
- V1: predicted "straight drops". F-150 straight drops 0.00899→0.00800 ✓. Mach-E straight drop is negligible (bias ~1 mrad/s); V1 effectively a no-op for Mach-E. Pass with caveat.
- V2: predicted "steady drops". Both platforms: Mach-E steady 0.0315→0.0298, F-150 steady 0.0363→0.0287. ✓ Both.

## Schema checks
- `out/FORD_MUSTANG_MACH_E_MK1/sim_V2.csv` → PASS
- `out/FORD_F_150_LIGHTNING_MK1/sim_V2.csv`  → PASS

## Surprise
The two Fords pull the gain in **opposite directions**: Mach-E needs `g≈1.09` (KS under-predicts ψ̇), F-150 needs `g≈0.87` (KS over-predicts). Both are per-platform; a single workshop-wide gain would damage one. Likely physical: F-150's effective steer-axis compliance + heavier mass + softer truck rubber means real road-wheel angle is smaller than `delta_wheel/i_s`. Mach-E has stiffer rear (rear-biased layout) and likely a small understeer KS doesn't model, so true yaw exceeds KS. This is exactly why rule 8 demands per-platform fits.
