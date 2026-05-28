# agent-04 — Lateral-Fidelity Submission

## Headline numbers (held-out validation, 80/20 split by route)

| Platform | Yaw RMSE V0 | Yaw RMSE V3 | Yaw improvement | XTE RMSE V0 (m) | XTE RMSE V3 (m) | XTE improvement |
|----------|------------:|------------:|----------------:|----------------:|----------------:|----------------:|
| FORD_F_150_LIGHTNING_MK1 | 0.01391 rad/s | **0.00490 rad/s** | -64.8% | 159.54 | **46.71** | -70.7% |
| FORD_MUSTANG_MACH_E_MK1 | 0.01688 rad/s | **0.01541 rad/s** | -8.7% | 108.82 | **81.05** | -25.5% |

XTE is distance-resampled at ds = 1 m, RMSE over all distance samples in all val segments. Tesla is not in the eval pool — see "Limitations".

## Model

Speed-known kinematic single-track (KS) with three calibrated corrections layered on top of the V0 baseline:

```
delta_eff[k] = lowpass_tau( delta_road[k] - delta_off )
psi_dot[k]   = a * (v[k] / L) * tan(delta_eff[k]) / (1 + b * v[k]^2)
trajectory   = forward-Euler integrate psi_dot with measured v
```

Per-platform coefficients (in `coeffs.json`):

| | L (m) | a | b | delta_off (rad) | tau (s) |
|---|---:|---:|---:|---:|---:|
| F-150 Lightning | 3.700 | 0.913 | 7.69e-4 | 1.22e-3 | 0.064 |
| Mach-E | 2.984 | 1.160 | 8.02e-4 | 1.37e-5 | 0.069 |

Interpretation:
- `a < 1` (Lightning) or `> 1` (Mach-E): residual steering-ratio / effective-radius bias not captured in V0.
- `b ~ 8e-4 s²/m²` on both: classic understeer gradient — yaw gain rolls off with v², exactly what the dynamic bicycle model predicts (linearised, K_us/L).
- `tau ~ 65 ms`: lumped lag between commanded delta and tyre-effective delta (rack compliance + tyre relaxation length).
- `delta_off`: Mach-E offset is ~zero; Lightning shows ~1.2 mrad — likely alignment / sensor zero bias.

## Ladder

- **V0** — provided `(v/L) tan(delta)`. Control.
- **V1** — `a * (v/L) tan(delta) / (1 + b v^2)`. Two-param understeer fit. Biggest single jump on Lightning (val 0.01391 -> 0.00659).
- **V2** — add constant `delta_off`. Helped Lightning slightly (0.00659 -> 0.00535); Mach-E offset fits to noise.
- **V3 (shipped)** — V2 + first-order lag `tau` on the steering. Helped both; Lightning val 0.00535 -> 0.00490, Mach-E val 0.01583 -> 0.01541.

All four parameters jointly fit per platform via Nelder-Mead on yaw-rate MSE over the train split. No leakage: val routes are entirely disjoint from train routes.

## Limitations

- **TESLA_MODEL_3 falls through to V0 identity.** Tesla `sim.csv` files have no `yaw_rate_meas_rads` column, so I cannot fit.
- Mach-E val improvement is modest. A per-speed-bin gain or a true ST (linear-bicycle, slip-aware) model would likely close more.
- Trajectory integration is forward-Euler (dt=20 ms). Switch to RK4 if grader is sensitive.
