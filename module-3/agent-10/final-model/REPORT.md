# Final model — agent-10 (rung-0, per-segment δ₀, platform-gated)

See parent dir REPORT.md and EXPERIMENTS.md for full provenance.

## Headline (full data/sim/, 1996 segments, pooled)
- yaw_rate_rmse: 0.005874 rad/s  (vs V0 0.01293, -54.6%)
- cte_rmse:      56.81 m         (vs V0 163.83,  -65.3%)

## Per-platform (pooled)
| platform | n_seg | yaw_rmse (V0 → V1) | cte_rmse (V0 → V1) |
|---|---|---|---|
| FORD_F_150_LIGHTNING_MK1 | 175 | 0.01633 → 0.00566 (-65%) | 157.51 → 62.19 (-61%) |
| FORD_MUSTANG_MACH_E_MK1  | 240 | 0.01362 → 0.00859 (-37%) | 148.00 → 98.68 (-33%) |
| HYUNDAI_IONIQ_5          | 800 | 0.01770 → 0.00766 (-57%) | 247.50 → 69.53 (-72%) |
| TESLA_MODEL_3            | 781 | 0.00000 (V0 passthrough — no truth) |

## Model
Per-platform reconstruction shape:
- delta_eff = (delta_road_rad − δ₀) · g
- yr_ss     = v · delta_eff / (L_eff + K_us · v²)
- yr        = first-order lag(yr_ss, τ) (discretised over segment dt)
- (x, y)    = forward Euler of (v · cos ψ, v · sin ψ) with ψ = ∫yr dt

δ₀ is platform-gated:
- Lightning: single global δ₀ (per-segment hurt it; stable steering offset)
- Mach-E and IONIQ-5: per-segment δ₀ from input-only straight-row gate
  (|yaw_rate_pred_rads| < 0.03 ∧ v > 5, median delta_road_rad, ≥ 50 rows)
- Tesla: V0 passthrough (no truth channel to score against)

Coefficients are the published top-tier-cohort values; Nelder-Mead refit
shaved <2% pooled yaw RMSE and produced a degenerate g↔L_eff fit on
Mach-E. Coeffs frozen at the recipe values. See EXPERIMENTS.md E01–E04.

## Rung-1 attempt
Linear dynamic single-track (vy, yr ODE) with C_αf-only fit (other params
from carParams). On a 60-segment subset: -5.8% yaw on IONIQ-5, -1.1% on
Mach-E with C_αf pegging the upper bound. Not robust enough in 45-min
budget. Logged as EXPERIMENTS.md E04, fell back to rung 0.
