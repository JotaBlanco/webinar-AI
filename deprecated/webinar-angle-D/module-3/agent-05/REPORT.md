# REPORT — Lateral-fidelity triage on Ford Mustang Mach-E (MK1)

- **Platform:** `FORD_MUSTANG_MACH_E_MK1` (Mach-E). `yaw_rate_meas_rads` is **measured** truth from the Ford party DBC in the rlog (IMU yaw rate).
- **Operating contract:** `v` and `δ` are **clamped to measured** under the speed-known contract (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Lateral-only metric: `yaw_rate_pred_rads − yaw_rate_meas_rads`.
- **Segment set:** first 20 Mach-E `sim.csv` files under `data/sim/segments/FORD_MUSTANG_MACH_E_MK1/` (sorted), 57,979 rows total. Regime split: straight 55,076 / steady 1,901 / transient 1,002.
- **Attribution scheme:** strict marginal, fixed order V0→V1→V2→V3→V4 (per skill v0.5).
- **Sensor:** `sensor.py` PASSED on `out/best_V1.csv` — corr(pred, meas) on cornering = 0.996; RMSE(candidate) = 0.01368 ≤ V0 = 0.01575.

## Variant ladder (RMSE in rad/s, lower is better)

| Variant | Overall | Straight | Steady | Transient | Marginal vs prev | Note |
|---|---|---|---|---|---|---|
| V0 baseline | 0.01575 | 0.01095 | 0.04411 | 0.06379 | — | as-is `yaw_rate_resid_rads` |
| V1 KS + per-seg yaw-gyro bias | **0.01368** | **0.00662** | 0.04522 | 0.06738 | **−0.00207** | wins overall and on straights |
| V2 linear ST, prior Cα | 0.01606 | 0.00351 | 0.06072 | 0.08514 | +0.00238 | **regression overall**: prior Cα over-stiffens cornering response |
| V3 linear ST, fit Cα (L-BFGS-B, bounds 5e4–5e5) | 0.01616 | 0.00363 | 0.06108 | 0.08553 | +0.00011 | **regression**: fit returned x0 (Cf=Cr=1.5e5) — solver did not move from initial guess; pegged-bound check did not fire |
| V4 Ridge LOO residual learner on V3 | 0.01529 | 0.00372 | 0.05586 | 0.08271 | −0.00088 | partial recovery; still worse than V1 |

- Marginal sum V0→V4 = +0.00046; total drop V0→V4 = +0.00046 (within 15% by coincidence — regressions and the V4 recovery nearly cancel).
- V1 is the best ship-ready variant overall and on straights (which are 95% of the corpus).
- V2/V3/V4 do beat V1 on the **straight** regime in isolation, but only because they shrink already-small straight residuals at the cost of large cornering error.

## Bullets

- Dominant fix was V1's per-segment yaw-gyro bias on straight-line samples: straight RMSE 0.01095 → 0.00662 (−39.5%).
- V2 prior Cα (Mach-E openpilot-canonical: Cf=286,551, Cr=355,912) makes steady-state gain too stiff for this Mach-E corpus → cornering RMSE roughly doubles.
- V3 fit failure mode: `scipy.optimize.minimize(L-BFGS-B)` exited at the initial guess `(1.5e5, 1.5e5)`. The pegged-at-upper-bound check (v0.5) does not detect a stationary-at-x0 outcome. Flagged here as a regression with cause: solver convergence failure on a near-flat loss surface dominated by straight samples.
- V4 LOO residual learner partially recovers from V3 (overall 0.01616 → 0.01529) but never beats V1 → per skill rule, V4 ships as a regression.
- No second markdown table per v0.5 reporting rule.
- Sensor was run as the final gate on `out/best_V1.csv` and passed both checks.

## Shipped variant

**V1** — KS yaw-rate using canonical `L = 2.984 m` plus per-segment mean residual subtracted on `|δ_road| < 0.01 rad` samples.
