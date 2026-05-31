# agent-08 final-model report

## Model

**v1: speed-known kinematic bicycle + per-platform linear-understeer correction + steering-input lag compensation.**

Functional form:

    yaw_rate_pred(t) = alpha * v(t) * delta_road(t - tau) / (L * (1 + K * v(t)^2))

Three per-platform corrections sit on top of the V0 kinematic baseline
(`yr = v*delta/L`):

1. **K (linear-understeer coefficient, 1/(m/s)^2).** Standard steady-state
   understeer reduction: at higher speed the same steering angle produces
   less yaw rate because tyres slip. K is positive for both platforms.
2. **alpha (effective-steering scale, dimensionless).** Absorbs residual bias
   in the steering-ratio / road-wheel-angle conversion. The Mach-E needs
   alpha > 1 (V0 was under-predicting), the F-150 needs alpha < 1 (V0 was
   over-predicting), consistent with the per-platform `yr_meas/yr_kin`
   ratios observed in residuals.
3. **tau (steering-input lag, samples).** The V0 prediction visibly leads
   the truth by ~60-80 ms across both Ford platforms (cross-correlation
   peak shifted by 3-4 samples at 50 Hz). The lag is applied to the
   delta input.

Tesla is not graded (no `yaw_rate_meas_rads` truth channel), so the model
falls back to V0 (alpha=1, K=0, lag=0) on that platform -- defensible
placeholder.

## Coefficients (fit on 75/25 train/dev split, Ford segments only)

| Platform                  |    L (m) |    K (1/(m/s)^2) |  alpha  | lag (samples) |
|---------------------------|---------:|-----------------:|--------:|--------------:|
| FORD_F_150_LIGHTNING_MK1  |     3.70 |          0.00095 |  0.9634 |             3 |
| FORD_MUSTANG_MACH_E_MK1   |    2.984 |          0.00085 |  1.1778 |             4 |

Fit method: for each (lag, K) on a grid, solve the optimal alpha
analytically as the least-squares scale (`alpha* = <x,y>/<x,x>` with
`x = v*delta_lag / (L*(1+K*v^2))`, `y = yr_meas`), then take the
(rmse, lag, K, alpha) tuple with minimum pooled yaw-rate RMSE on the
training half. Dev half is for sanity, not for selection.

## Results vs V0 (full Ford eval set, 415 segments)

| KPI                                   |    V0    |   v1   | delta   |
|---------------------------------------|---------:|-------:|--------:|
| Yaw-rate RMSE (rad/s)                 |  0.01479 | 0.00821 | -44.5%  |
| Distance-resampled CTE RMSE (m)       |   151.99 |  117.59 | -22.6%  |

Per-platform yaw-rate RMSE:

| Platform                  |    V0    |   v1   |  delta  |
|---------------------------|---------:|-------:|--------:|
| FORD_F_150_LIGHTNING_MK1  |  0.01633 | 0.00702 | -57.0%  |
| FORD_MUSTANG_MACH_E_MK1   |  0.01362 | 0.00895 | -34.3%  |

Per-platform CTE RMSE:

| Platform                  |    V0    |   v1   |  delta  |
|---------------------------|---------:|-------:|--------:|
| FORD_F_150_LIGHTNING_MK1  |  157.51  | 109.31 | -30.6%  |
| FORD_MUSTANG_MACH_E_MK1   |  148.00  | 123.08 | -16.8%  |

Per-regime yaw-rate RMSE (v1):

| Regime    | RMSE (rad/s) | n_samples |
|-----------|-------------:|----------:|
| straight  |      0.00686 |   884,752 |
| steady    |      0.01192 |   128,289 |
| transient |      0.01793 |    33,124 |

Train/dev split was consistent: dev RMSE within 5% of train RMSE on both
platforms, so the per-platform fit is not overfitting on this data
volume.

## Why these specific corrections

- **K > 0 (understeer):** the F-150 ratio `yr_meas/yr_kin` averaged 0.65
  in moderate steering -- a 35% steady-state shortfall that scales with
  v^2, exactly the linear-bicycle understeer signature. Mach-E showed a
  much milder version (ratio ~0.95). Heavier, longer-wheelbase vehicle
  understeers more, as expected.
- **alpha:** even after K, a constant scale remained between truth and
  the model -- the F-150 model still over-shoots by a few percent
  (alpha=0.96) and the Mach-E undershoots by ~18% (alpha=1.18). The
  Mach-E figure is the largest single correction in the model and
  suggests the openpilot steerRatio prior on the Mach-E may be slightly
  off, or the delta_road_rad channel in the sim CSVs is computed with a
  ratio that under-estimates the road-wheel response.
- **tau (lag):** a deterministic shift of the input -- not a dynamic
  first-order delay. Tried higher-order delay models but the simple
  sample shift captured most of the gain.

## What was tried and not shipped

- A dynamic first-order steering filter `delta_eff' = (delta - delta_eff)/T`:
  marginally lower RMSE than the discrete sample shift, not worth the extra
  parameter for the data we have.
- Per-segment K-tuning: overfits dev. Per-platform is the right granularity.

## Skill use

- `score-model/score.py`: used as-is, drives every iteration's evaluation.
- `_shared/traj_metrics.py`: used for the CTE math, not modified.
- `pre-flight-final-model`: used as-is to confirm the bundle is shaped right.
- `load-segments`, `visualise-segment`, `compare-models`, `make-train-dev-split`:
  bypassed -- ran the same logic inline in ~50 lines of scratch scripts.

## Known limitations

- Tesla has no truth channel; the model ships V0 for it.
- The model is purely lateral -- v is taken as measured. Matches the
  workshop's "speed-known" framing.
- Transient regime is still the highest-RMSE regime. A linear bicycle
  with yaw-rate dynamics (a tau on the output, not the input) would
  likely help further.
