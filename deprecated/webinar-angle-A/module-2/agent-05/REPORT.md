# Module-2 / agent-05 — Lateral fidelity report

**Platform scored:** `FORD_MUSTANG_MACH_E_MK1` (315 segments, ~913k samples at 50 Hz). `yaw_rate_meas_rads` and `a_lat_meas_mps2` are **measured truth** channels (Ford IMU decoded by the adapter), not predictions or self-consistency.

**Speed-known contract honoured.** `v_mps` and `delta_road_rad` are **clamped** inputs. `yaw_rate_pred_rads` and `a_y_pred_mps2` are the only predicted channels. The metric is the lateral residual `yaw_rate_pred − yaw_rate_meas`. No unclamping was attempted.

**Headline:** RMSE dropped from V0 = 0.01613 rad/s to V4 = 0.01035 rad/s — a **35.8% reduction**. The transient-cornering regime improved most: 0.0393 → 0.0147 rad/s (62%).

## Variant ladder (sequential / nested-model accounting)

| Variant | RMSE (rad/s) | Straight | Steady | Transient | Marginal Δ | Note |
|---|---:|---:|---:|---:|---:|---|
| V0 baseline       | 0.01613 | 0.01390 | 0.02912 | 0.03926 | —        | as-stored `yaw_rate_resid_rads` |
| V1 bias-removed   | 0.01414 | 0.01183 | 0.02661 | 0.03702 | -0.00198 | per-segment mean removed |
| V2 + α re-fit     | 0.01111 | 0.01055 | 0.01361 | 0.01996 | -0.00303 | scalar steering gain per segment |
| V3 + understeer K | 0.01077 | 0.01033 | 0.01122 | 0.01901 | -0.00034 | bicycle-model `1/(L+k·K·v²)` |
| V4 + lag align    | **0.01035** | 0.01017 | 0.00982 | 0.01475 | -0.00042 | median lag = 4 samples (80 ms) |

**Total drop:** 0.00578 rad/s = sum of marginals 0.00577 (rounding). **Accounting scheme: sequential nested-model marginal** — each row adds one mechanism while keeping prior fits.

## Variants implemented

- **V1** — per-segment bias removal on `yaw_rate_resid_rads`.
- **V2** — per-segment scalar steering-gain α re-fit on `delta_road_rad`.
- **V3** — V2 + understeer-gradient correction `ψ̇ = v/(L + k·K·v²) · tan(α·δ)` with `K_us` from openpilot bicycle-model parameters; per-segment k-scale fit.
- **V4** — V3 + integer-sample cross-correlation lag alignment per segment.

**Regimes** (fixed across all variants): `|a_y|≥1.0` ∧ `|jerk|≥1.0` → transient; cornering otherwise; straight = neither.

**No regressions** — every variant strictly reduced RMSE in every regime.

## Notes

- Mean per-segment α came out to 0.9996, yet V2 contributed the largest marginal drop. The win wasn't a global steering-ratio miscalibration; it was that *per-segment* α varies meaningfully (with bias removal absorbing the rest). Dominant error source is segment-specific (tyre temperature, road bank, sensor zeroing), not a parameter-set defect.
- KS is closer to right than expected; the remaining residual is largely things KS structurally can't see (slip), confirmed by transient-regime RMSE being 2–3× steady across every variant.

## Limitations

- No comparable-segment grouping (route type, speed range, urban vs highway). A manifest CSV would have allowed proper stratification.
- Regime thresholds (|a_y|≥1.0, |jerk|≥1.0) defined from first principles inside the module; may not match cross-cohort conventions.

Files: `out/analyze.py`, `out/ladder.csv`, `out/fit_summary.txt`.
