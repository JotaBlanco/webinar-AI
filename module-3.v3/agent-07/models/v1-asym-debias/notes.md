# v1-asym-debias — asymmetric gain + signed-bias offset

## Formulation

```
delta_raw = delta_road_rad − δ₀                       (V1's per-segment δ₀)
w_left    = 0.5 · (1 + tanh(delta_raw / eps))         ∈ [0,1], eps = 0.005
g_eff     = g_left · w_left + g_right · (1 − w_left)
delta     = delta_raw · g_eff
yr_ss     = v · delta / (L_eff + K_us · v²)
yr_lag[i] = yr_lag[i−1] + α[i] · (yr_ss[i] − yr_lag[i−1])   α = dt/(τ+dt)
yr_out    = yr_lag + b_offset · 1[v > 2]              (gated additive bias)
```

## State-space

State: scalar `yr_lag` (V1's lagged yaw rate).
Inputs: same 8-column allowlist as V1.
Initial condition: `yr_lag[0] = yr_ss[0]`.
Integrator: explicit first-order lag (V1's), trivially stable.

## Parameters (per platform)

| platform | g_left | g_right | b_offset | L_eff | K_us | τ |
|---|---|---|---|---|---|---|
| Lightning | 0.8570 | 0.8672 | 0.0      | 3.26   | 0.0035 | 0.060 |
| Mach-E    | 0.8968 | 0.8615 | +0.00121 | 2.22   | 0.0015 | 0.069 |
| IONIQ-5   | 0.9474 | 0.9219 | +0.00029 | 2.887  | 0.0029 | 0.062 |

Tesla: V0 passthrough (no truth → cannot fit; honest fallback).

Fitting protocol:
1. Fit (g_left, g_right) per platform by Nelder-Mead minimising
   `yaw_rmse/yaw_v1 + 0.5·cte_rmse/cte_v1` on first 80 segments.
2. Fit b_offset on top by extending the same loss to all 3 parameters.
3. **Halved** b_offset on Mach-E/IONIQ-5 and zeroed it on Lightning to
   guard against subset-fit overshoot — Lightning's full-dataset bias was
   already at threshold (+0.00012) so any imposed offset hurts.

## Expected residual character (the V1 residual it attacks)

V1 leaves two structural residuals on this dataset:

1. **Direction asymmetry** — on Mach-E and IONIQ-5, V1 substantially under-
   predicts right turns (right-turn bias −0.0072 / −0.0055) vs near-zero on
   left turns. V1's single `g` cannot fix this; the asymmetric gain
   does (each direction's gain re-calibrated independently).

2. **Residual signed yaw bias** — even after the gain split, ~half of the
   right-turn bias survives on Mach-E (-0.0014 → +0.0003 after this model).
   That residual is a *velocity-independent* offset, dominated by the platforms
   where δ₀ alone wasn't enough. A small gated additive bias closes it.

## Why this is structurally different from V1

- V1 is a single-scale steering map: `delta_eff = g · (delta − δ₀)`. It has
  no functional dependence on the *sign* of delta_eff. Asymmetric gain
  introduces that dependence; it cannot be obtained by re-fitting V1's coefs.
- V1's δ₀ correction acts before the gain, so it adds a constant to the
  steering input. The `b_offset` here adds a constant to the *yaw output*
  after the lag, which is a different transfer function.

## Known limitations

- The b_offset is fitted on yaw bias but its *purpose* is to reduce CTE drift
  (CTE = double integral of yaw error). A more principled approach would fit
  b_offset directly against CTE. We use yaw as a proxy.
- The asymmetry might be route-distribution-induced (more right turns in dev).
  Not validated against a clean L/R-balanced subset.
- Does not address the transient-regime yaw RMSE (0.0164), which is V1's
  largest residual class. That class requires real dynamic-ST machinery (rung 1).
