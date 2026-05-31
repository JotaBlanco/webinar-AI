# Lateral fidelity model — agent-05

## Approach

Per-platform steady-state-understeer bicycle model with first-order yaw lag, fit on a whole-route 75/25 train/dev split via Nelder-Mead. Tesla passthrough (no truth channel for the F-150-only/Mach-E-only fits).

Model, evaluated per sample on the segment time grid:

    delta_eff[k] = g * delta_road[k] + delta_offset
    yr_ss[k]     = v_meas[k] * delta_eff[k] / (L + K_us * v_meas[k]^2)
    yr_pred[k]   = (1 - alpha[k-1]) * yr_pred[k-1] + alpha[k-1] * yr_ss[k]
    alpha[k]     = dt[k] / (tau + dt[k])

`L` is fixed to the openpilot-canonical wheelbase prior; `(g, delta_offset, K_us, tau)` are fit per platform. Trajectory `(x, y)` is integrated zero-order-hold from `(yr_pred, v_meas)` exactly as `_shared/traj_metrics.integrate_trajectory` does, so the prediction is self-consistent with the CTE metric.

## Fitted coefficients

| Platform | g | δ₀ (rad) | K_us | τ (s) | L (m) |
|---|---|---|---|---|---|
| FORD_MUSTANG_MACH_E_MK1 | 1.1936 | +0.000164 | 0.00275 | 0.0701 | 2.984 |
| FORD_F_150_LIGHTNING_MK1 | 0.9786 | −0.001231 | 0.00398 | 0.0604 | 3.70 |

Notes:
- Mach-E `g = 1.19` indicates the V0 steer ratio underestimates effective road-wheel response by ~20%; this single correction is the biggest source of the Mach-E gain.
- F-150 `K_us = 0.00398` is the highest, consistent with its heavier, longer-wheelbase signature called out in `anti-patterns.md`.
- `τ ≈ 60–70 ms` matches the prior in `approach-menu.md`.
- All four fits sit inside the loose bounds; none pegged (per `anti-patterns.md` warning about tool priors).

## Results — full Ford set (415 segments)

| Model | Yaw RMSE | CTE RMSE | F-150 yaw | F-150 CTE | Mach-E yaw | Mach-E CTE |
|---|---|---|---|---|---|---|
| V0 baseline | 0.01479 | 151.998 | 0.01633 | 157.5 | 0.01362 | 148.0 |
| V1 (this)   | **0.00779 (-47%)** | **101.699 (-33%)** | 0.00566 | 62.4 | 0.00899 | 122.0 |

Per-regime yaw RMSE (V0 -> V1):
- straight: 0.0095 -> 0.0063
- steady:   0.0281 -> 0.0116
- transient: 0.0382 -> 0.0179

Held-out dev (105 segments, whole-route split, seed=42): yaw -35.8%, CTE -21.2%. Smaller gain on dev than on full set as expected; both KPIs still improve materially. No regression on either platform on either KPI.

## Variants tested and rejected

**V2 — polynomial steering `g(δ) = g₀ + g₁·|δ|`**. Train RMSE for Mach-E dropped from 0.0091 to 0.0075 (-17%) but dev CTE *increased* 2 m and dev yaw improved only ~3%. Classic overfit signature flagged in `anti-patterns.md`; not shipped. The Mach-E nonlinearity hinted at in `approach-menu.md` is real but small and the polynomial doesn't generalise to dev with only this much data.

## What this leaves on the table

`two-kpi-tradeoff.md` says: when yaw improvement is much larger than CTE improvement (here -47% vs -33% — and -34% vs -18% on Mach-E specifically), residual *systematic* bias is still present. The remaining error is concentrated on Mach-E. Plausible next steps:
- Speed-dependent or `a_lat`-dependent understeer `K_us(v, a_lat)`.
- Fuse `a_lat_meas_mps2 / v_meas` as a second yaw-rate estimate via a complementary filter.
- A small residual learner trained on `[v, |δ|, |a_lat|]` — bounded feature count, ridge-regularised, cross-validated per route.

None were tried in the time budget.

## Reproducing

- `work/fit_model.py` — fits V1 coeffs from `data/` and writes `final-model/coeffs.json`.
- `work/eval_v1.py` — scores V0 and V1 on dev and full.
- `final-model/predict.py` loads `coeffs.json` at import time; the grader can call `predict(sim_df, platform)` directly.
