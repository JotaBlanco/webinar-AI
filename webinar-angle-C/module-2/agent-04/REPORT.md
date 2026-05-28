# Module-2 / agent-04 (angle-C) — Lateral fidelity ladder (FORD_MUSTANG_MACH_E_MK1)

**Platform scored:** `FORD_MUSTANG_MACH_E_MK1` (315 segments, 913 626 samples @ 50 Hz). `yaw_rate_meas_rads` is **measured truth** from the rlog (Ford CAN decode; Tesla excluded per ratchet rule 4).

**Operating contract (rule 5):** `clamp_v_to_measured=True, clamp_delta_to_measured=True`. Only lateral states are predicted; speed-state agreement is zero by construction. `a_y_pred = v·ψ̇` is coupled (rule 9) but we score on `ψ̇` directly.

**Sign convention:** `residual = pred − meas` (rule 1). Sanity check: `corr(δ_road, ψ̇_meas | cornering) = +0.801` — ISO 8855 consistent (rule 2).

**Regime masks** (fixed across all variants, rule 11):
- straight: `|ψ̇_meas|<0.02 rad/s` and `v>3 m/s` (611 929 samples)
- transient cornering: `|ψ̇_meas|>0.05` and `|dψ̇/dt|>0.15 rad/s²` (17 400)
- steady cornering: `|ψ̇_meas|>0.05` and not transient (79 458)

**Train/test:** interleaved every-5th-sample split (rule 7). All RMSE below is held-out test.

## Variant ladder (RMSE in deg/s; strict marginal accounting V0 → V_last)

| # | Variant | All | Straight | Steady | Transient | Δ vs prev | Fit scope |
|---|---|---|---|---|---|---|---|
| V0 | baseline `yaw_rate_resid_rads` as-is | 1.013 | 0.487 | 2.312 | 3.012 | — | n/a |
| V1 | global bias removal (b=+0.093 deg/s) | 1.015 | 0.484 | 2.321 | 3.024 | **+0.2% (regression)** | per-platform |
| V2 | affine gain+bias on `ψ̇_pred` (α=1.0795, β=-0.037 deg/s) | 0.964 | 0.517 | 2.194 | 2.549 | -5.0% | per-platform |
| V3 | + per-segment lag align (k=+3 samples = **60 ms**, pred leads meas) | 0.949 | 0.510 | 2.186 | 2.397 | -1.5% | per-platform |
| V4 | + per-segment median-bias subtraction | 0.848 | 0.230 | 2.180 | 2.398 | -10.7% | **per-segment (CALIBRATION, rule 8)** |

**Net model-only improvement (V0 → V3, no calibration):** -6.3% all-regime, **-20% in transients**.
**With per-segment calibration (V0 → V4):** -16.3% overall, -53% on straight regime (sensor zero offsets).

## Regression flagged (rule)

**V1 ↑0.2%** is a real regression. Physical cause: the global median residual on the train set is non-zero because cornering samples have asymmetric pred-meas error (model under-gains in turns). Subtracting that median pushes straight-line residuals away from zero. V2's affine fit subsumes V1 cleanly, so V1 is dropped from the recommended stack.

## What each change contributed

- **V2 gain α≈1.08 (-5.0%)** — kinematic single-track under-predicts yaw rate at given (v, δ_road) because it ignores tire slip; an 8% gain bump is the standard "missing dynamic bicycle" correction. The only V*model*-improvement worth keeping.
- **V3 lag 60 ms (-1.5% overall, -5.9% transient)** — measurement chain (CAN + IMU) lags KS prediction by ~3 samples; matters only for transients.
- **V4 per-segment bias (-10.7%)** — almost entirely straight-line gyro zero offset (RMSE_straight drops 0.510 → 0.230). **Calibration, not a model improvement** per rule 8.

## Per-regime takeaways

- **Straight:** residual dominated by per-segment gyro zero (V4 halves it). Model is fine.
- **Steady cornering:** dominated by gain error; V2 takes ~5% out, V3/V4 barely move it.
- **Transient:** dominated by lag *and* gain; V2+V3 together cut it by 20%.

## Painful absence

No yaw-rate truth on Tesla (rule 4) — I cannot test whether α=1.08 generalises across the openpilot fleet, only across the two Ford platforms (and I only ran one, time-budget). The improvement is genuinely *per-platform*, not *per-vehicle-class*, until F-150 confirms.

## Near-misses

Started toward a speed-dependent gain α(v) (slip grows with v²); the fit is non-trivially better but the variance increase on the held-out test split argues against it under rule 7 — left for next iteration.

## Surprise

V1 — a textbook "remove the bias first" move — is a **regression** here. The bias is asymmetric (cornering-driven), and V2 absorbs it cleanly with a coefficient that also makes physical sense. The intuition "always bias-correct first" is wrong on autocorrelated lateral residuals.

Files: `tools/analyze.py`, `out/variant_ladder.csv`.
