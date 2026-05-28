# Plan — 20260527T135842Z (LOCKED)

## Variant ladder (fixed order, one DoF per rung, cumulative)

| # | Variant | Physical hypothesis | DoF added | Predicted direction | Falsifiable success criterion |
|---|---------|---------------------|-----------|---------------------|-------------------------------|
| V0 | baseline KS | `ψ̇ = (v/L) tan δ`, clamped (v, δ) | 0 | — | reference |
| V1 | per-segment IMU bias (straight) | yaw-gyro has segment-constant DC offset | 1 per segment | RMSE drops on straight; near-zero change on cornering | if straight RMSE does not drop substantially, hypothesis wrong |
| V2 | linear ST, prior C_α | tyre slip — steady-state gain `ψ̇ = v·δ / (L·(1+K_us·v²))` with `v<2 m/s` KS fallback | tyre model swap (no new free param) | RMSE drops on steady cornering; transient may worsen | if steady RMSE doesn't drop, openpilot priors are wrong direction |
| V3 | linear ST, fit C_α (1D scale on K_us) | priors miscalibrated for these tyres/roads | 1 (scalar K_us) | further drop on steady; bound peg → flag the linear-ST form itself | if pegged at 50/500 kN/rad, flag regression |
| V4 | ridge residual on `[v, \|a_y\|, \|δ\|, sign(δ̇)]`, LOSO | structured-but-unmodelled effects (load transfer, banking, slip nonlinearity) | 4 features + intercept, ridge λ=10 | drops transient regime most; in-fold scoring would be dishonest, so LOSO only | if LOSO drop ≤ 0 anywhere, learner is laundering noise |

## Attribution scheme

- Strict marginal in locked order V0→V4. Marginal_i = RMSE(V_{i-1}) − RMSE(V_i) on the same mask.
- Marginal drops must sum to within 15% of total V0→V4 drop; >15% means double-counting or instability — reported as a flag.

## Regime mask (fixed, applied identically to every variant)

- straight: `|delta_road_rad| < 0.01`
- steady cornering: `|delta_road_rad| ≥ 0.01` ∧ `|d(delta_road)/dt| < 0.05`
- transient cornering: `|delta_road_rad| ≥ 0.01` ∧ `|d(delta_road)/dt| ≥ 0.05`

## What would invalidate this plan

- `sign_corr` negative on cornering → stop, fix sign before any variant scoring.
- V3 C_α pegging at a bound → report V3 as a regression flag; do not silently extend the bound.
- V4 LOSO marginal drop < 0 in any regime → report as failed residual learner, not a fix.

## Locked at: 20260527T135842Z
