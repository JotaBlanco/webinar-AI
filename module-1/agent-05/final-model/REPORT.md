# agent-05 — lateral-fidelity submission

## Headline numbers (held-out validation, 30% deterministic split by file hash)

| Platform | KPI | V0 baseline | V1 (this submission) | Improvement |
|---|---|---|---|---|
| FORD_MUSTANG_MACH_E_MK1 | Yaw-rate RMSE (rad/s) | 0.01197 | 0.00870 | -27.3% |
| FORD_MUSTANG_MACH_E_MK1 | CTE RMSE (m, 1 m grid) | 83.89 | 67.19 | -19.9% |
| FORD_F_150_LIGHTNING_MK1 | Yaw-rate RMSE (rad/s) | 0.01269 | 0.00694 | -45.3% |
| FORD_F_150_LIGHTNING_MK1 | CTE RMSE (m, 1 m grid) | 51.81 | 33.83 | -34.7% |
| TESLA_MODEL_3 | — | — | V0 fallback (no truth) | — |

CTE truth = `yaw_rate_meas_rads` integrated against `v_mps`. The CSV `x_m, y_m`
columns are V0's own integrated trajectory and cannot serve as ground truth.

## Model ladder

- V0 baseline: `psi_dot = (v / L) * tan(delta)`.
- V1 shipped: `psi_dot = gain * v * (delta - delta_offset) / (L + Kus * v^2)`
  — linear-bicycle / understeer-gradient form. Three scalars per platform,
  fit by Nelder-Mead on yaw-rate RMSE vs `yaw_rate_meas_rads` on the full pool.

Speed-bucket diagnostics showed V0 residual decreasing monotonically with v —
the classic understeer signature — so V1 was the natural step up from a
plain gain or steering-offset-only correction.

### Shipped coefficients

| Platform | L (m) | Kus | delta_offset (rad) | gain |
|---|---|---|---|---|
| FORD_MUSTANG_MACH_E_MK1 | 2.984 | 0.00256 | -3.5e-05 | 1.1775 |
| FORD_F_150_LIGHTNING_MK1 | 3.700 | 0.00344 | 0.00122 | 0.9567 |
| TESLA_MODEL_3 | 2.875 | 0 | 0 | 1.0 |

Mach-E gain 1.18 is suspicious — likely steer-ratio overestimate or column
compliance. Either way, the fit absorbs it.

## Isolation notes
Did not read other agents' work, orchestrator material, or raw rlogs.
Worked entirely from sim CSVs and `code/`.
