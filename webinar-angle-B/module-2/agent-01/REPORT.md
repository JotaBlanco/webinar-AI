# Module-2 / agent-01 (angle-B) — Lateral fidelity variant ladder

## Scope and contract

- **Platforms scored:** `FORD_MUSTANG_MACH_E_MK1` (315 segs) and `FORD_F_150_LIGHTNING_MK1` (230 segs). Tesla excluded — no decoded truth.
- **Truth channel:** `yaw_rate_meas_rads` from the Ford CAN DBC (`opendbc/ford_lincoln_base_pt`). Measured by the chassis IMU/ESC stack, not a model self-consistency check.
- **Speed-known contract:** `v_mps` and `delta_road_rad` are clamped to measurement at every integration step. The predicted channel under test is `yaw_rate_pred_rads`. Residual sign: `pred − meas`.
- **Segment set & regime mask identical across V0..V3.** Regimes: straight (|ψ̇|<0.05 rad/s), steady (cornering, |ψ̈|<0.2 rad/s²), transient (cornering, |ψ̈|≥0.2). Pooled RMSE sample-weighted.

## Variant ladder (cumulative)

| Variant | What changes |
|---|---|
| V0 | Baseline: `yaw_rate_resid_rads` from `sim.csv`, no preprocessing |
| V1 | V0 + per-segment yaw-rate bias removal |
| V2 | V1 + per-segment steering→yaw latency alignment (integer-sample shift, xcorr peak on cornering, ±8 samples = ±160 ms) |
| V3 | V2 + replace KS kinematic gain with ST steady-state gain `ψ̇ = v·δ / (L·(1+K_us·v²))`, K_us from `PARAM_BY_PLATFORM` |

K_us: Mach-E 5.6e-4 s²/m, Lightning 4.5e-4 s²/m (both understeer-positive).

## Results — Ford Mustang Mach-E MK1 (RMSE in mrad/s)

| Variant | straight | steady | transient | all (pooled) | Δ vs prev (all) |
|---|---|---|---|---|---|
| V0 | 9.01 | 27.15 | 44.72 | **13.16** | — |
| V1 | 5.31 | 25.56 | 42.23 | **10.73** | -2.44 (-18.5%) |
| V2 | 5.23 | 25.34 | 38.23 | **10.44** | -0.29 (-2.7%) |
| V3 | 4.27 | 29.67 | 46.25 | **11.57** | +1.14 (+10.9%) **regression** |

Best variant for Mach-E: **V2** (-20.7% vs V0).

## Results — Ford F-150 Lightning MK1 (RMSE in mrad/s)

| Variant | straight | steady | transient | all (pooled) | Δ vs prev (all) |
|---|---|---|---|---|---|
| V0 | 10.25 | 32.92 | 39.80 | **15.84** | — |
| V1 | 8.53 | 30.14 | 38.55 | **14.16** | -1.68 (-10.6%) |
| V2 | 8.45 | 29.92 | 36.48 | **13.95** | -0.21 (-1.5%) |
| V3 | 4.93 | 16.32 | 22.53 | **7.92** | -6.03 (-43.2%) |

Best variant for Lightning: **V3** (-50.0% vs V0). The ST upgrade collapses cornering residual by ~50% on the truck.

## V3 regression on Mach-E — physical cause

The ST steady-state gain de-amplifies KS yaw rate by `1/(1+K_us·v²)`. On the Lightning, KS over-predicts cornering yaw rate (heavier vehicle, longer wheelbase, larger lateral compliance) and the ST correction is in the right direction. On the Mach-E, the KS prediction was already biased *low* on cornering peaks — most of the cornering error is *not* a simple gain error but high-frequency content from suspension/tyre dynamics KS can't see. De-amplifying further with K_us>0 worsens both cornering bins.

## Painful absence

A **shared evaluation module with the regime definitions pinned**. AGENTS.md+CLAUDE.md are 23 KB of conventions re-paid every turn but neither pins regime thresholds or a pooled-RMSE function. Had to invent `|ψ̇|<0.05, |ψ̈|<0.2` — defensible but not blessed. Also had to hand-copy K_us inputs from `code/parameters.py` (symlinked `code/` isn't import-clean).

## Rule-prevented near-misses

- Almost ran a per-platform K_us calibration that would have made V3 win on Mach-E. The prior comes from `carParams` and calibrating-on-the-same-data-we-score-on would be a leak. Held off; flagged as V4-future on a held-out split.

## Most surprising

**Per-segment yaw-rate bias is large, consistent, physical.** Median +1.1 mrad/s on Mach-E, +3.3 mrad/s on Lightning. Real sensor offsets / integration drift. Removing them collapses straight-line RMSE by ~40%. Expected the headline win to come from physics (V3); on Mach-E the cheapest preprocessing dominates. The truck is where the linear-tyre upgrade pays off.

Files: `out/analyse.py`, `out/plot_variants.py`, `out/variant_rmse.png`, `out/per_segment_*.csv`, `out/summary.json`.
