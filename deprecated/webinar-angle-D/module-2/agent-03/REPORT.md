# REPORT — webinar-angle-D / module-2 / agent-03

**Task:** Improve KS lateral (yaw-rate) prediction on Ford and attribute the gains.
**Platform scored:** `FORD_MUSTANG_MACH_E_MK1` (Mach-E). Truth channel: `yaw_rate_meas_rads` is **measured** from the rlog IMU (Ford party DBC).
**Sample:** 25 segments, 72,477 rows (seeded sample of 315 Mach-E sims).
**Operating contract:** speed-known, lateral-only (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Residual under test = `yaw_rate_resid = pred − meas`.

## Variant ladder

| Variant | Overall RMSE (rad/s) | Straight | Steady cornering | Transient | Δ vs prev (overall) |
|---|---:|---:|---:|---:|---:|
| V0 — CSV baseline (`yaw_rate_pred_rads`) | 0.01277 | 0.00924 | 0.01699 | 0.04689 | — |
| V1 — KS w/ canonical `L` + per-segment yaw-gyro bias on straights | **0.01133** | **0.00627** | 0.01702 | 0.04819 | **−0.00144 (−11.3%)** |
| V2 — Linear ST, prior `C_α` (286.6k / 355.9k N/rad) + per-seg bias | 0.01204 | 0.00436 | 0.02083 | 0.05268 | +0.00071 (worse) |
| V3 — Linear ST, fit `C_α` (bounded 5e4–5e5 N/rad) + per-seg bias | 0.01224 | 0.00443 | 0.02134 | 0.05309 | +0.00020 (worse) |
| V4 — V3 + Ridge residual learner on `[v, \|a_y\|, \|δ\|, sign(δ̇)]` (LOO) | 0.01273 | 0.00458 | 0.02252 | 0.05423 | +0.00049 (worse) |

Regime counts: straight 59,103 / steady 11,845 / transient 1,529.

## Attribution

- **V1 (canonical-L KS + per-segment straight-regime yaw bias)**: −0.00144 rad/s overall (−11.3%). Effectively a per-segment yaw-gyro zero-offset correction. Straight RMSE falls 32% (0.00924 → 0.00627); steady and transient are essentially unchanged. This is the only variant that *helps*.
- **V2 (linear ST, prior Cα)**: +0.00071 rad/s. The understeer-gradient denominator `1 + K_us·v²` is non-zero (Mach-E is rear-biased: `l_r·C_αr − l_f·C_αf > 0`), so it slightly attenuates yaw vs KS at highway speeds. With the truth channel matching KS well already, attenuation = regression.
- **V3 (linear ST, fit Cα)**: +0.00020 vs V2. The loss surface is monotone toward Cα → ∞ (which is exactly KS). `fit_c_alpha` (L-BFGS-B from `x0=[1.5e5,1.5e5]`) returns the initial guess because the local gradient is shallow; a coarse grid search confirms the bounded optimum sits at (5e5, 5e5) — i.e. the optimiser wants to *become* KS, but is held inside the prior box. Bottom line: there's no linear-ST sweet spot for Mach-E on this corpus.
- **V4 (Ridge residual learner, LOO)**: +0.00049 vs V3. The residuals look segment-specific (driver style, road grade, suspension warm-up) and don't generalise across segments under leave-one-out CV. Ridge with `[v, |a_y|, |δ|, sign(δ̇)]` adds noise on held-out segments.

## What actually fixed things

Stock `yaw_rate_pred_rads` in `sim.csv` already equals the canonical KS formula `(v/L)·tan(δ)` with the openpilot Mach-E `L=2.984 m` (corr=1.0 vs recomputation, RMSE diff ≈1e-7). So "KS recalibration" is a no-op on this corpus. The *real* gain in V1 is the **per-segment yaw-gyro bias subtraction on straight-line samples** (`|δ_road| < 0.01 rad`). That single offset accounts for the entire −11.3% improvement and tells us the dominant lateral residual is a near-DC gyro-mount/zero bias, not a slip-dynamics effect.

## Sign-error spot-check

`corr(δ_road, ψ̇_meas)` on cornering segments: 0.98–0.99 across spot-checked routes. No sign error.

## Caveats / limitations

- Scored on a 25-segment seeded sample (seed=0) of 315 Mach-E segments — not the full corpus.
- Transient regime is only 2% of samples (1,529 rows). Its RMSE moves but the row count is too low for confident attribution.
- `fit_c_alpha` as shipped relies on L-BFGS-B from a single seed; on this corpus that's effectively a no-op. A multi-start or DE pass would resolve it but wouldn't change the conclusion — the linear-ST rung is the wrong tool here.
- F-150 Lightning not scored. Lateral truth channel exists for it too; would likely show the same picture (bias-dominated) but heavier mass.

## Most painful missing component

`references/` with a one-line note that `yaw_rate_pred_rads` in the published CSV is already canonical KS. The skill currently makes V1 sound like a re-derivation upgrade; in reality V1's whole value is the bias subtraction. Five minutes lost confirming this by hand.
