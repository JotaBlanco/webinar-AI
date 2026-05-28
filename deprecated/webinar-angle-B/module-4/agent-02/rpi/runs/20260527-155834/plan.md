# Plan — 20260527-155834

## Variant ladder (locked)

| # | Variant | Physical hypothesis | DoF added | Predicted direction | Falsifiable success criterion |
|---|---------|---------------------|-----------|---------------------|-------------------------------|
| V0 | baseline | `yaw_rate_resid_rads` as-is | 0 | — | reference |
| V1 | per-segment bias on straights | KS cannot correct IMU yaw-gyro offset; subtract mean residual on `|δ|<0.01` per segment | 1 (one constant per segment, estimated on straights) | RMSE drops most on **straight** regime; if it doesn't, the offset hypothesis is wrong | `RMSE_straight(V1) < RMSE_straight(V0)` |
| V2 | linear-ST gain, prior `C_α` | KS misses understeer gradient; ST steady-state gain `ψ̇ = v·δ / (L·(1 + K_us·v²))` should close part of the cornering residual using openpilot priors | 1 (model form upgrade, no new fitted parameter) | RMSE drops on **steady cornering**; transient may worsen because we only changed the steady-state map | `RMSE_steady(V2) < RMSE_steady(V1)` |
| V3 | linear-ST, fit `(C_αf, C_αr)` | Even ST only helps if `C_α` matches these tyres on these roads; refit OLS on steady samples, bounds 50–500 kN/rad | 2 (two fitted scalars) | Marginal drop on **steady cornering** beyond V2; if either pegs the bound, the linear-ST form is wrong (regression flag) | `RMSE_steady(V3) < RMSE_steady(V2)` and neither `C_α` pegs |

## Attribution scheme

Strict marginal in the locked V0→V3 order, computed on **all-regime RMSE**.
Marginal drops sum to within 15 % of total (V0_all − V3_all); >15 % means
double-counting or instability. Per-regime drops are also reported but the
canonical "credit" column is on the all-regime metric to avoid regime-cherry-
picking.

## Regime mask (fixed, applied identically to every variant)

- straight: `|δ_road| < 0.01`
- steady cornering: `|δ_road| ≥ 0.01 ∧ |dδ/dt| < 0.05`
- transient cornering: `|δ_road| ≥ 0.01 ∧ |dδ/dt| ≥ 0.05`

Computed once on V0 inputs; identical across all variants.

## What would invalidate this plan

- Sign-sanity correlation negative → stop, fix adapter, restart.
- V1 makes straight RMSE *worse* → IMU offset is not the dominant straight
  bias; ship the partial and flag.
- V3 pegs either bound → linear-ST form is wrong, report as regression flag
  rather than a clean win.

## Locked at: 20260527-155834
