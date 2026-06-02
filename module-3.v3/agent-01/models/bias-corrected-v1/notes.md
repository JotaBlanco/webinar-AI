# bias-corrected-v1

## Formulation
For each non-Tesla platform p:
```
yaw_rate_pred_corrected = predict_v1(sim_df, p).yaw_rate_pred_rads + b_p
```
where `b_p` is a fitted scalar yaw-rate offset (rad/s).

## State-space / inputs
Inputs: identical to V1 (8-column allowlist). Output: V1's predicted yaw rate plus a constant per-platform scalar.

## Why this attacks V1's residual
V1's per-platform signed yaw residual on dev:
- Mach-E: -0.00142 rad/s, with -22.0 m signed CTE drift.
- IONIQ-5: -0.00075 rad/s, with -11.6 m signed CTE drift.
- Lightning: +0.00012 rad/s, +0.3 m CTE drift (no correction needed).

CTE is a double-integral of yaw error along the path. Persistent yaw bias accumulates a heading offset that grows like (bias * distance), and cross-track error grows roughly like (bias * distance^2 / 2). Killing that signed bias is the highest-leverage move *if* V1's RMSE residual is bias-dominated, which it is on Mach-E and IONIQ-5 (yaw_bias_fraction reported by score-model is small here, but the slow integration amplifies it).

## Integrator / fitting
Offline sweep of `b_p` over [-0.0005, +0.003] rad/s minimising pooled per-platform CTE RMSE on `data/sim/segments/`. Best:
- Mach-E: +0.00210 rad/s
- IONIQ-5: +0.00108 rad/s
- Lightning: 0 (already centred)

## Why this is `differs-from-v1`
The model has an extra output term V1 cannot produce by re-fitting its coefficients. V1's coefficient family controls a multiplicative steady-state gain (v·delta / (L+K·v²)) and a first-order temporal lag; none of those can produce a constant additive yaw-rate offset.

## Expected residual character after correction
- Mean yaw residual should move toward zero on Mach-E and IONIQ-5.
- Pooled CTE should drop; yaw RMSE moves slightly (offsetting bias trades off against std).
