# agent-08 — lateral-fidelity ship

## Model

Per-platform kinematic-single-track steady-state yaw rate with a polynomial steering scale, fitted offset, speed-quadratic understeer term, and a single first-order yaw lag:

    g(delta) = g0 + g2 * delta^2
    yr_ss    = v * (g(delta)*delta - delta0) / (L + K_us * v^2)
    yr(t)    = first_order_lag(yr_ss, tau)

Parameters fit per-platform on all FORD_* segments, optimising sample-pooled yaw-rate MSE on samples where v > 2 m/s. Tesla is V0 passthrough (no truth channel).

## Fitted coefficients

| platform                  | L     | g0     | g2    | delta0    | K_us    | tau   |
|---------------------------|-------|--------|-------|-----------|---------|-------|
| FORD_MUSTANG_MACH_E_MK1   | 2.984 | 1.1477 | 0.966 | -2.7e-05  | 0.00232 | 0.072 |
| FORD_F_150_LIGHTNING_MK1  | 3.70  | 0.9356 | 0.372 |  1.17e-03 | 0.00327 | 0.063 |

Mach-E has a large g0 > 1 (the openpilot prior under-rates effective steering authority once the steering ratio is folded in) and pronounced curvature in g(delta). Lightning is closer to neutral g0 but with a larger K_us, consistent with the heavier truck running more understeer.

## Headline numbers (agent-internal scoring)

V0 vs ship, ALL FORD segments (n=415), sample-pooled yaw RMSE with v > 2 m/s, distance-resampled CTE RMSE:

|              | yaw RMSE (rad/s) | CTE RMSE (m) |
|--------------|------------------|--------------|
| V0 baseline  | 0.01479          | 152.0        |
| ship (V2)    | 0.00720          | 101.9        |
| relative     | -51%             | -33%         |

Per platform on the full data:
- Mach-E: yaw 0.01362 -> 0.00828 (-39%), CTE 148.0 -> 122.8 (-17%)
- Lightning: yaw 0.01633 -> 0.00527 (-68%), CTE 157.5 -> 61.0 (-61%)

Per-regime yaw RMSE (ship):
- straight: 0.0063
- steady: 0.0096
- transient: 0.0147

Held-out whole-route dev (~25%, n=106): yaw 0.0067, CTE 89.6 — consistent with full-data figures; no overfit signal.

## Two-KPI reading

Lightning is a win-both, ship-it case. Mach-E shows the textbook asymmetry: yaw gain (-39%) outpaces CTE gain (-17%). Per the two-KPI doc this is residual coherent bias accumulating in heading. delta0 and polynomial g already absorbed most of the steering-static bias, so the remainder is most likely in the transient regime where a single-tau first-order lag underfits a real second-order steering-response chain. That's where the next gain lives — linear dynamic ST or a second-order lag.

## What I tried that did not help

- **Complementary fusion with a_lat_meas / v**: optimal alpha ~ 0-0.01 per platform. The lateral-accel channel is noisier than the physics prediction; fusion is net-zero.
- **Residual linear regressor** on `[1, v*delta, v*delta^3, delta_dot, v*delta_dot, slip_proxy, |delta|*delta]`: ~1.5% in-sample gain, worse held-out CTE on Mach-E. Dropped.
- **Speed-linear K_us(v) = K0 + K1*v**: K1 ~ 1e-5, no meaningful effect.

## Anti-pattern compliance

- Per-platform fits: yes, two parameter sets.
- Bias trick alone: no — delta0 is a global model parameter, not a per-segment subtraction at inference.
- Whole-route holdout: yes for validation; final fit uses all data.
- Tesla: V0 passthrough.
- No per-segment-fitted parameters at inference.

## Files

- `predict.py` — exports `predict(sim_df, platform) -> pd.DataFrame`.
- `coeffs.json` — fitted parameters loaded at module import.
- `manifest.json` — declares platform support and entry point.
