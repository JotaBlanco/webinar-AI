# Lateral-Fidelity Triage — REPORT

- Platform: **FORD_MUSTANG_MACH_E_MK1** (Ford Mach-E MK1).
- `yaw_rate_meas_rads` is the **measured** truth channel from the rlog (Ford party DBC).
- Operating contract: `v` and `δ` are **clamped to measured** every step (speed-known, lateral-only).
- Residual under test: `yaw_rate_pred_rads − yaw_rate_meas_rads`, all in rad/s.
- Segment set: first 60 Mach-E `sim.csv` files under `data/sim/segments/FORD_MUSTANG_MACH_E_MK1/`.
- Accounting: **strict marginal**, fixed order V0 → V1 → V2 → V3 → V4. Δ = RMSE(prev) − RMSE(curr). Sum of marginals = total drop (1.000×, within 15% tolerance).
- Sensor (`skills/lateral-fidelity-triage/sensor.py`) on best variant: **PASS** sign-consistency (corr = +0.994 cornering), **PASS** regression-check (0.01005 ≤ V0 0.01214).

| Variant | Overall RMSE | Straight | Steady | Transient | Δ vs prev | Verdict |
|---|---|---|---|---|---|---|
| V0  baseline (existing `yaw_rate_resid_rads`)                | 0.01214 | 0.00851 | 0.02519 | 0.04889 | —        | reference |
| V1  KS recalibrated + per-segment yaw-gyro bias              | 0.01055 | 0.00506 | 0.02602 | 0.05116 | −0.00159 | improvement (carried by straight-line bias subtraction) |
| V2  Linear ST with prior C_α                                 | 0.01248 | 0.00335 | 0.03424 | 0.06362 | +0.00193 | **regression** — ST prior C_α too stiff for these tyres; transient and steady both worsen |
| V3  Linear ST with fit C_α (Cf=150 000, Cr=150 000 N/rad)    | 0.01260 | 0.00343 | 0.03458 | 0.06398 | +0.00012 | **regression** — optimizer stalled at x0; loss non-convex due to K_us pole at l_r·C_αr ≈ l_f·C_αf. Not pegged at upper bound, so v0.5 pegged-check did not flag |
| V4  Ridge residual learner on V3 (LOO out-of-fold)           | 0.01005 | 0.00351 | 0.02544 | 0.05382 | −0.00255 | **best**; sensor passes |

- Sign correlation `corr(pred, meas)` is +0.99x on cornering across all variants — no sign flip anywhere.
- V1 wins almost entirely on the straight regime (0.00851 → 0.00506) — per-segment yaw-gyro bias subtraction. Recalibrating L to the canonical 2.984 m contributed marginally.
- V2/V3 worsen both steady and transient regimes because the Mach-E openpilot-canonical priors (C_αf = 286 551, C_αr = 355 912) make `v·δ / (L·(1 + K_us·v²))` softer than KS `tan(δ)` on these rlogs. Fitting C_α did not help — L-BFGS-B never moved from its `(1.5e5, 1.5e5)` start because the surface around the K_us-zero locus is non-smooth.
- V4 recovers below V0 by re-learning what V3 broke. OOF Ridge on `[v, |a_y|, |δ|, sign(δ̇)]` rebuilds most of the missing dynamic content. Net honest gain over V0 is 0.00210 rad/s (~17%).
- Painful absence in the skill: the v0.5 pegged-Cα rule only guards the **upper** bound. Here the fit stalled mid-range; no rule catches "optimizer didn't move from x0" or "K_us pole nearby in parameter space." Candidate addition for v0.6.
- v0.4 low-v fallback (`v_min ≈ 2 m/s` → KS) fired silently on stationary Mach-E samples; without it V2/V3 RMSE would have exploded.
- Recommendation: ship V4. V1 is the right physics-only fallback. V2/V3 are honest regressions and must not be shipped.
