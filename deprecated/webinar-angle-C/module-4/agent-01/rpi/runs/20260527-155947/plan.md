# Plan — 20260527-155947

LOCKED at 20260527-155947. Implementation may not reorder this ladder.

## Variant ladder (Mustang primary; F-150 cross-check)

| # | Variant | Physical hypothesis | DoF added | Predicted direction | Falsifiable success criterion |
|---|---------|---------------------|-----------|---------------------|-------------------------------|
| V0 | baseline | none — `yaw_rate_resid_rads` as-is | 0 | — | reference |
| V1 | bias removal (per-platform) | constant IMU/steering-zero offset | 1 | small overall improvement (≤1e-3 rad/s); strongest on straight | if straight RMSE does not drop, V1 did not address what I claimed |
| V2 | scalar gain on pred (per-platform) | KS understeers vs. real car — needs scalar steady-state gain | 1 | large improvement on steady & transient; small on straight | if steady RMSE drops <30% relative, hypothesis falsified |
| V3 | 1-sample lag alignment of pred to meas | CAN-vs-sim timestamp offset (~20 ms) | 1 | improvement concentrated in transient | if transient does not improve, lag is not the dominant transient cause |

All parameters fit on **train (4/5)**, scored on **test (every 5th sample)**. All fits **per-platform**, not per-segment.

## Attribution scheme

Strict marginal in fixed order V0 → V1 → V2 → V3 on the held-out test set. Marginal drop = `RMSE(V_{i-1}) − RMSE(V_i)`. Coherence: `|Σ marginal − total|/|total| < 0.15`.

## Regime mask (identical for every variant)

- straight: `|delta_road_rad| < 0.01`
- steady cornering: `|delta_road_rad| ≥ 0.01 ∧ |d δ/dt| < 0.05`
- transient cornering: `|delta_road_rad| ≥ 0.01 ∧ |d δ/dt| ≥ 0.05`

## What would invalidate this plan

- V2 worsens straight by more than V1 improved it → gain absorbs bias and bias removal was redundant.
- Coherence > 15% → double-counting; investigate before shipping.
- Sign-flip on `corr(δ_road, ψ̇)` after a transform → `schema_check.py` would catch.
