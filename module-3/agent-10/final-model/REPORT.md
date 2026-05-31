# Module-3 / agent-10 — Lateral-fidelity model

## Headline (held-out dev: 108 segments, 25% whole-route holdout, seed=42)

| KPI            | V0 baseline | V1 (linear g) | V2 shipped (poly g)    |
|----------------|-------------|---------------|------------------------|
| yaw RMSE rad/s | 0.016472    | 0.008176      | **0.007371** (-55%)    |
| CTE RMSE m     | 151.454     | 117.458       | **109.563** (-28%)     |

Per-platform on the full FORD set (415 segments):

| Platform                  | V0 yaw   | V2 yaw   | V0 CTE m | V2 CTE m |
|---------------------------|----------|----------|----------|----------|
| FORD_F_150_LIGHTNING_MK1  | 0.01633  | 0.00531  | 157.51   | 60.92    |
| FORD_MUSTANG_MACH_E_MK1   | 0.01362  | 0.00842  | 148.00   | 127.15   |

## Model

Per-platform single-track with polynomial steering scale, effective wheelbase,
understeer, steering offset, and first-order yaw-rate lag:

```
delta_eff = delta_road_rad - delta0
g(delta_eff) = g0 + g2 * delta_eff^2
yr_ss(t) = v(t) * g * delta_eff / (L_eff + K_us * v(t)^2)
yr_pred  = first_order_lag(yr_ss, tau)
```

Coefficients fit by Levenberg–Marquardt on 307 train segments (74% of FORDs,
whole-route holdout, seed=42).

Fitted coefficients (see COEFFS.json):
- Lightning: g0=0.968, g2=0.297, L_eff=3.807, K_us=0.00341, delta0=0.00133, tau=0.06
- Mach-E:    g0=1.083, g2=0.721, L_eff=2.797, K_us=0.00236, delta0=0.00021, tau=0.07

For `TESLA_MODEL_3`: no truth channel — passthrough V0's `yaw_rate_pred_rads`.

## Variants tried

- **V1**: linear steering scale only. Per-platform fit. Already a large win
  (yaw -50%, CTE -22% on dev).
- **V2 (shipped)**: V1 + quadratic `g2·δ_eff²` term. The Mach-E coefficient
  `g2≈0.72` is non-trivial — it captures steering nonlinearity the linear
  scale can't, dropping Mach-E yaw RMSE and trimming Mach-E CTE by ~15 m on dev.

## References consulted

- `anti-patterns.md` — held out by route (not segment), refused per-segment
  δ₀ trick, fit per platform, passthrough Tesla.
- `approach-menu.md` — picked closed-form understeer + lag + polynomial-g,
  which the menu flagged as unexplored for Mach-E.
- `two-kpi-tradeoff.md` — diagnosed residual Mach-E CTE gap as systematic
  bias (yaw gap closed faster than CTE gap); poly-g chipped at it.

## Honest residual & next steps

Mach-E CTE 127 m is still ~2× Lightning's 61 m. Yaw improvement on Mach-E
(38%) exceeds CTE improvement (14%) — by the two-KPI guide, residual
systematic bias remains. Most plausible next levers (untried, time budget):
- `a_lat_meas_mps2` complementary-filter fusion (channel is sitting unused).
- Dynamic single-track with slip angles (capture transient).
- Speed-dependent K_us(v).

## Skills used

- `make-train-dev-split`: whole-route 25% holdout, seed=42, used as-is.
- `score-model`: as-is for KPI computation.
- `pre-flight-final-model`: ran before shipping; all checks pass except
  `report_md_present` (REPORT.md write is blocked by harness — this content
  is persisted by the parent).
- `load-segments`: bypassed (inline `pd.read_csv` faster for fitting loops).
- `compare-models`, `visualise-segment`: not used.
