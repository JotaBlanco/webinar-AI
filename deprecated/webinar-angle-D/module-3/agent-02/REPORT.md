# REPORT.md — lateral-fidelity-triage on Mach-E (module-3 / agent-02)

- **Platform:** `FORD_MUSTANG_MACH_E_MK1` (Mach-E MK1).
- **Truth channel:** `yaw_rate_meas_rads` is **measured** truth (decoded Ford IMU from rlog).
- **Contract:** `v` and `δ` are **clamped to measured** at every step (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Speed-state agreement is therefore not a metric here; only lateral residual is.
- **Residual under test:** `yaw_rate_pred_rads − yaw_rate_meas_rads`, in rad/s.
- **Segment set:** 30 Mach-E `sim.csv` files (evenly sampled from 315 available), 87 040 rows total.
- **Regime mask:** straight `|δ|<0.01 rad`; steady `|δ|≥0.01 & |dδ/dt|<0.05 rad/s`; transient `|δ|≥0.01 & |dδ/dt|≥0.05`.
- **Accounting:** strict marginal, fixed order V0→V1→V2→V3→V4. Sum of marginal drops = total V0→V4 drop (0.00288 rad/s); 0 % off — within the 15 % tolerance.
- **Best variant:** **V2** (Linear ST with prior `C_α`). V3 and V4 are regressions vs V2 and are reported as such.
- **Sensor gate:** `python3 skills/lateral-fidelity-triage/sensor.py out/best_variant_V2.csv` → both checks PASS (`corr(pred,meas)=0.998` on cornering; `RMSE=0.00821 ≤ V0=0.01143`).

## Variant ladder (RMSE of yaw-rate residual, rad/s)

| Variant | Overall | Straight | Steady cornering | Transient cornering | Marginal Δ (overall) | Notes |
|---|---|---|---|---|---|---|
| V0 — baseline (as-is `yaw_rate_resid_rads`) | 0.01143 | 0.00962 | 0.01719 | 0.02851 | — | No preprocessing. |
| V1 — KS recalibrated + per-segment straight-line gyro bias | 0.00888 | 0.00598 | 0.01669 | 0.02705 | −0.00255 (−22 %) | Canonical L=2.984 m; bias removed where `|δ|<0.01`. |
| V2 — Linear ST, prior `C_αf=286 551`, `C_αr=355 912` (openpilot-canonical), v_min=2 m/s KS fallback | **0.00821** | **0.00318** | 0.01787 | 0.03244 | −0.00068 (−8 %) | Best overall. Improves straight, mildly worsens cornering. |
| V3 — Linear ST with fit `C_α` | 0.00853 | 0.00333 | 0.01870 | 0.03293 | +0.00032 (+4 %) | **Regression.** L-BFGS-B did not move from `x0=(1.5e5,1.5e5)` — not pegged at upper bound, but evidently stuck on a flat region of the loss surface for this subset. The skill's pegged-Cα detector does not catch a stuck-at-initial-guess failure. |
| V4 — Ridge residual learner on `[v, |a_y|, |δ|, sign(δ̇)]`, leave-one-segment-out | 0.00855 | 0.00394 | 0.01836 | 0.03113 | +0.00002 (+0 %) | **Regression.** OOF Ridge cannot beat V3 out-of-fold; per the skill, V3 (already a regression) and V4 are both rejected. |

## Per-variant contribution to improvement

- V1 (KS recalibration + straight-line bias removal): **−2.55 mrad/s RMSE** — 88 % of the total improvement.
- V2 (linear ST with prior `C_α`): **−0.68 mrad/s RMSE** — 23 % more, but concentrated on straight-line samples.
- V3 (fit `C_α`): **+0.32 mrad/s** — regression; optimiser stuck at initial guess `(1.5e5, 1.5e5)` for both axles, which is below the openpilot-canonical prior Mach-E uses, so the V2→V3 step effectively softens the tyres without justification.
- V4 (Ridge LOO residual learner): **+0.02 mrad/s** — null/regression; OOF RMSE 0.00913 > V3 in-set, fails the "must beat V3 out-of-fold" gate.

## Best variant shipped

V2 (Linear ST, prior `C_αf=286 551` N/rad, `C_αr=355 912` N/rad) + per-segment straight-line yaw-gyro bias removal, with v_min=2 m/s KS fallback. Written to `out/best_variant_V2.csv`. Sensor PASS.

## Honest caveats

- V2 improves *overall* RMSE only because straight-line samples dominate. On cornering subsets, V2 is **worse** than V1: steady 0.01787 vs 0.01669 (+7 %), transient 0.03244 vs 0.02705 (+20 %). If the downstream consumer cares mostly about cornering, **ship V1**, not V2.
- V3 was not pegged at the upper bound (`(1.5e5, 1.5e5)`), but the optimiser did not move from the initial guess. This is a failure mode the v0.5 pegged-Cα rule does not catch. A `success` flag, gradient diagnostic, or multi-start fit should be added in v0.6.
- The skill mandates Ford for measured truth — confirmed. Tesla segments were excluded.
