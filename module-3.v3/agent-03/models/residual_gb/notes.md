# residual_gb — V1 + gradient-boosted residual correction

## Formulation

```
yr_pred(t) = yr_v1(t) + GB_platform(phi(t))
```

where `yr_v1` is the V1 baseline (kinematic-single-track + understeer + first-order lag + per-segment δ₀) and `GB_platform` is a `HistGradientBoostingRegressor` trained per platform on the V1 yaw residual `yr_truth - yr_v1`.

### Features (phi)

All allowlist-safe (no truth columns):
- `delta_road_rad`
- `d(delta_road_rad)/dt` (numpy.gradient over `t_s`)
- `v_mps`
- `yaw_rate_pred_rads` (V0 baseline, used as a regime feature)
- `yr_v1` (our V1 prediction, recomputed inside)
- `v_mps * yaw_rate_pred_rads` (allowlist a_lat proxy)
- `a_long_mps2`

### State-space / integrator

No state in the GB head — purely sample-wise. V1 supplies the dynamics; GB learns the residual the closed-form V1 cannot reach.

### Expected residual character attacked

Diagnosis (see `out/diagnose.py`):
- 30-44% of V1's pooled yaw RMSE² lives in transient regime (`|d_delta/dt| > 0.05`) on all three platforms.
- Residual is correlated with `delta` (corr -0.21 Mach-E, -0.21 Lightning, -0.10 Ioniq) and `yr_v0` (Mach-E -0.13), pointing at a structural gain/lag mismatch.
- High-`|a_lat|` segments are <1% of rows; tyre saturation is **not** the dominant residual on this dataset.

A purely linear residual model captured only R²=2-5% — the structure is non-linear (transient × delta × v interactions). Tree-based regression is well-matched.

## Why this differs structurally from V1

- V1 is a closed-form ODE in continuous gain and a single-pole lag. A linear refit of its 5 parameters buys ≤1% (verified empirically in `models/v1_refit`).
- GB head injects non-linear input-dependent corrections: piecewise gain on `delta`, piecewise lag effect via `d_delta`, regime-switched correction via `v` and `a_lat_proxy`. It strictly contains V1 (correction → 0 collapses to V1).
- Composes cleanly with V1's δ₀ correction (we recompute it per-segment inside).

## Identifiability / overfit risk

- Per-platform model trained on full available data (after 400k row subsample if larger). Out-of-route holdout (80/20 route-grouped) showed yaw 2-13% and CTE 14-51% better than V1 on held-out routes — improvement generalises.
- Tesla has no truth; falls through to V0 passthrough via V1.

## Knobs

- `max_iter=200, max_depth=5, learning_rate=0.05, min_samples_leaf=200, l2_regularization=1e-3`.
- Sub-sampled to 400k rows for fit speed; full data scored for evaluation.
