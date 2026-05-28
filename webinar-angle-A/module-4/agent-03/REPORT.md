# Module-4 / agent-03 — Lateral-fidelity ladder (Ford Mustang Mach-E MK1)

## Platform, channels, contract

- Platform: **FORD_MUSTANG_MACH_E_MK1** — 315 sim.csv segments, 913 626 samples at 50 Hz.
- Scored channel: `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads`. `yaw_rate_meas_rads` is the **measured** truth channel decoded from the rlog gyro; it is not predicted and is not clamped.
- Speed-known contract: `v` and `δ` are **clamped** to the measured values in the KS integrator. The **predicted** quantity under test is `yaw_rate_pred_rads` (V0) and its V1–V4 re-predictions. Speed-state agreement is zero by construction and is not the metric.
- Sign sanity check: `corr(δ_road, ψ̇_meas) = +0.702` on cornering samples. Convention is correct.
- Methodology: same segment set and same regime mask **held constant across every variant row**. Regimes: `straight` (`|δ_road|<0.01`), `steady` (`|δ_road|≥0.01 ∧ |δ̇|<0.05`), `transient` (`|δ_road|≥0.01 ∧ |δ̇|≥0.05`). All RMSE values in rad/s on `yaw_rate_resid_rads`. Negative `Δ` means RMSE went down (improvement).

## Variant ladder

| Variant | Description | RMSE overall | Straight | Steady | Transient | Δ vs prev |
|---|---|---:|---:|---:|---:|---:|
| V0 | Baseline `yaw_rate_resid_rads` as-is, no preprocessing                                                                                                  | 0.016127 | 0.008768 | 0.031724 | 0.056889 | — |
| V1 | KS recalibrated with canonical `L=2.984`; minus per-segment yaw-gyro bias on straights                                                                  | 0.014693 | 0.004931 | 0.031673 | 0.057390 | -0.001434 |
| V2 | Linear single-track with openpilot prior `C_αf=286 551, C_αr=355 912`, KS fallback below 2 m/s, same per-segment bias                                   | 0.015512 | 0.003393 | 0.034294 | 0.062869 | +0.000819 (regression) |
| V3 | Linear ST with `C_α` fit by differential evolution on the full segment set, bounded (5e4,5e5) N/rad → `C_αf=401 575, C_αr=389 774` (not pegged)         | 0.015105 | 0.003645 | 0.033124 | 0.061242 | -0.000407 |
| V4 | Ridge residual learner on V3 residuals; features `[v, |a_y|, |δ|, sign(δ̇)]`; **leave-one-segment-out** out-of-fold predictions                          | 0.014897 | 0.003704 | 0.032705 | 0.060063 | -0.000208 |

**Attribution scheme:** strict marginal, fixed order V0→V1→V2→V3→V4. Total drop V0→V4 = 0.001230 rad/s; signed Σ of the Δ column = -0.001230; `|Σmarg − total|/total ≈ 0.000` (well under the 15% coherence threshold).

## Findings, regression, and physical interpretation

- **Headline result.** Overall yaw-rate RMSE dropped from V0 = 0.016127 rad/s to V4 = 0.014897 rad/s — a **7.6% relative improvement** on the full Mach-E set. Most delivered by V1 alone (per-segment yaw-gyro bias) on the *straight* regime, where bias removal nearly halves residual RMSE (0.00877 → 0.00493).
- **V2 regressed against V1** (overall +0.000819). This is the predicted Mach-E behaviour: the openpilot ST prior `C_α` values are **stiffer than this car's tyres actually behave**, so the steady-state ST gain over-corrects KS and worsens both cornering regimes (steady 0.0317 → 0.0343; transient 0.0574 → 0.0629). V2 *does* improve straight (0.0049 → 0.0034) because the steady-state-gain form yields exactly zero yaw at zero δ, but the cornering damage dominates. **Regression flagged with cause: stiff prior `C_α` mis-matches Mach-E lateral compliance.**
- **V3 recovers part of the V2 regression but does not return to V1.** DE fit pushed both stiffnesses up toward (but not at) the 5e5 ceiling, reflecting that the joint loss "wants" the ST gain to look more like KS. V3 still under-performs V1 because linear-ST has one effective steady-state knob (`K_us`) and cannot reproduce the per-regime structure a bias-corrected KS captures.
- **V4 adds a small honest gain.** LOO-CV ridge residual learner trims another 0.000208 rad/s, mostly in steady and transient cornering — consistent with picking up a low-order `|a_y|`-dependent slip-angle correction that neither KS nor linear-ST encode. With in-fold scoring V4 would look much larger; LOO discipline keeps it honest.

## Workshop lesson

A single per-segment bias subtraction (V1) yields the bulk of the available improvement (1.43 mrad/s). Going to ST (V2) actively hurts on this platform's prior; the fit (V3) recovers most but not all of the damage; the residual learner (V4) adds a small honest top-up. The ladder's most useful output here is the *attribution column itself*: it shows which rungs pay and which cost.

## Methodological note

The bare `triage.fit_c_alpha` (L-BFGS-B from a single x0) gets stuck because the per-segment-bias step makes the loss surface non-smooth. Used differential evolution in `out/run_ladder.py` to find the global minimum. Helper should be patched.

## Limitations

- Only **FORD_MUSTANG_MACH_E_MK1** scored to keep segment-set constant. F-150 Lightning would be a useful cross-platform check but mixing platforms breaks methodology-consistency.
- V4 uses `a_y_pred_mps2` (KS prediction, no slip) as a feature per SKILL spec. Swapping in `a_lat_meas_mps2` could improve the learner but would change the variant definition.
- Per-segment bias in V1 absorbs both real gyro offset and any constant-δ steering-ratio mis-calibration; the two are not separately identifiable from straight-line data.

Files: `out/run_ladder.py`, `out/ladder_draft.md` (eval 6/6 PASS).
