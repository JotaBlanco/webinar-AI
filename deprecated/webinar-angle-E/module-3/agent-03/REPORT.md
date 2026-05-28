# REPORT.md — webinar-angle-E / module-3 / agent-03

## Platform & contract

- Platform: **FORD_MUSTANG_MACH_E_MK1**
- Truth channel: `yaw_rate_meas_rads` (Ford `sim.csv`)
- Operating contract: KS runs with `clamp_v_to_measured=True` and `clamp_delta_to_measured=True`. Speed and steering are inputs; the lateral residual `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` is the only metric.
- Corpus: 315 Mach-E `sim.csv` files, 913,626 rows total. Regime counts — straight 785,093, steady 106,978, transient 21,555.
- Attribution scheme: **strict marginal, fixed order V0→V1→V2→V3**, marginal drop per variant = RMSE(prev) − RMSE(this). Sum of marginals reconciles to the V0→V3 total (within 0%).

## Variant ladder (RMSE of `yaw_rate_resid_rads`, rad/s)

| Variant | Overall | Straight | Steady   | Transient | Marginal vs prev | Note |
|---------|---------|----------|----------|-----------|------------------|------|
| V0 raw `sim.csv` residual | 0.01613 | 0.00877 | 0.03173 | 0.05680 | — | baseline as-is |
| V1 KS recalibrated + per-segment straight-line gyro-bias removed | 0.01469 | 0.00493 | 0.03168 | 0.05730 | **−0.00143** | mean &#124;bias&#124; per segment ≈ 5.4 mrad/s; transient regresses mildly |
| V2 Linear-ST, openpilot prior `C_αf=2.87e5`, `C_αr=3.56e5` | 0.01653 | 0.00701 | 0.03450 | 0.06234 | **+0.00184** | drops bias-removal benefit; steady & transient both worse |
| V3 Linear-ST, fit `C_αf=C_αr=3.0e5` (bounds (5e4, 5e5), **not pegged**) | 0.01628 | 0.00729 | 0.03349 | 0.06114 | **−0.00025** | interior local min; multi-start required (single-start L-BFGS-B stalled at init) |

V0→V3 **total drop = −0.000155 rad/s (regression)**. Marginals: V1 +0.00143, V2 −0.00184, V3 +0.00025; sum = −0.000155. Reconciles to total exactly. (Within 15% gate trivially.)

## Attribution

- **V1 earned its delta on straight rows.** Per-segment yaw-gyro bias subtraction reduces straight-line RMSE by ~44% (8.77 → 4.93 mrad/s). Mean absolute per-segment bias ≈ 5.4 mrad/s — consistent with un-zeroed automotive gyros.
- **V2 destroyed it.** Switching from `tan(δ)` to `v·δ/(L(1+K_us v²))` re-introduces a straight-line offset (no gyro-bias term in the linear-ST kernel) and increases under-prediction in cornering. The Mach-E priors are stiffer than these tyres want at the relevant slip angles, so the gain is too low.
- **V3 partially un-breaks V2.** Fit `C_α` symmetrically at 3.0e5 N/rad — softer than the prior front (2.87e5 OK) and noticeably softer than the prior rear (3.56e5). **Not pegged** at either bound. Symmetric front/rear at the fit is a curiosity: with `l_f < l_r` (Mach-E rearward CG bias actually inverted here — `l_f=1.31, l_r=1.67`), the optimal `(C_f, C_r)` collapse to equal values, hinting that the loss surface is shallow along the `K_us` ridge.

### Sibling skill — per-regime contrast (`regime-comparison`)

| variant | Δ straight | Δ steady | Δ transient | dominant regime |
|---------|-----------:|---------:|------------:|-----------------|
| V1 | −0.00384 | −0.00005 | +0.00050 | straight (improvement) |
| V2 | −0.00176 | +0.00276 | +0.00555 | transient (regression) |
| V3 | −0.00148 | +0.00175 | +0.00435 | transient (regression) |

V2 and V3 both have *transient* as their dominant-regime impact, and both negatively — the linear-ST switch hurts most exactly where the residual was already worst.

## Regression flags (honest)

- **V2 vs V1 — net regression (+0.00184 overall).** Cause: linear-ST kernel has no per-segment bias term; the V1 gyro-bias removal is lost. Cornering gain (K_us) with prior `C_α` is too low for these tyres → systematic under-prediction in steady and transient.
- **V3 vs V0 — net regression (+0.00015 overall) despite fit `C_α`.** Cause: the fit cannot recover the lost gyro-bias, only reshape the cornering gain. The skill ladder is missing a "linear-ST + per-segment bias" rung; that's where the win lives.

## Recommendations (if the ladder could be extended)

- Add a V2b/V3b variant: linear-ST with the same per-segment straight-line bias subtraction used in V1. Expected to recover the −0.004 straight-line win lost at V2.
- Cross-validate the V3 `C_α` fit across held-out segments — current fit is in-sample.
- The symmetric `C_f = C_r = 3.0e5` fit is a smell. Suspect a flat loss along the `K_us` ridge; consider re-parametrising the optimiser in `(L, K_us)` instead of `(C_f, C_r)`.
