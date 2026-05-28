# Plan — 20260527-160000

## Variant ladder

| # | Variant | Physical hypothesis | DoF added | Predicted direction | Falsifiable success criterion |
|---|---------|---------------------|-----------|---------------------|-------------------------------|
| V0 | baseline | none | 0 | — | reference |
| V1 | per-platform yaw-rate bias `b` (subtract median residual fit on train) | constant gyro zero-offset / KS integrator bias | 1 per platform | drops straight-regime RMSE, modest on steady/transient | if straight RMSE does not drop ≥30%, gyro-bias hypothesis is wrong |
| V2 | per-segment yaw-rate bias `b_seg` | per-ignition IMU calibration drift | 1 per segment | further drops straight RMSE relative to V1; warning: this is calibration not model | if held-out (interleaved 5th sample) RMSE drop < V1's drop, V2 is over-fitting noise |
| V3 | per-platform steering-gain `k` on δ_road (ψ̇_pred = v·(k·δ)/L) | wheel-to-road ratio mis-set or rack compliance not modelled | 1 per platform | drops steady cornering RMSE most; mild on straight | if steady RMSE does not drop ≥20%, gain hypothesis is wrong |
| V4 | per-platform affine on δ: ψ̇_pred = v·(k·δ + δ0)/L, then bias on ψ̇ | combines V1 + V3 in the same fit (no double-counting) | 2 per platform | best on overall; transient drop is the diagnostic of headroom left for ST model | if transient RMSE doesn't drop, KS-limited (need dynamic ST) |

Attribution scheme: **strict marginal in fixed order V0→V1→V2→V3→V4**, RMSE^2 (variance) decomposition reported. Both per-platform (V1, V3, V4) and per-segment (V2) labels are stated explicitly.

## Regime mask (fixed)
- straight: |δ_road| < 0.01 rad
- steady: |δ_road| ≥ 0.01 and |dδ/dt| < 0.05 rad/s
- transient: |δ_road| ≥ 0.01 and |dδ/dt| ≥ 0.05 rad/s

## Train / test split
- Interleaved every-5th sample = TEST; remainder = TRAIN. Fit parameters on TRAIN only; report held-out TEST RMSE for all variants (rule 7).

## What would invalidate this plan
- V2 (per-segment bias) RMSE drop on held-out TEST exceeding V1 by a wide margin would suggest the bias is genuinely per-segment, not per-platform — flag as calibration finding, not model improvement.
- If V3's gain k is close to 1.0 (say |k−1|<0.02), the steering-ratio hypothesis is wrong; we ship the partial.

## Locked at: 20260527-160000
