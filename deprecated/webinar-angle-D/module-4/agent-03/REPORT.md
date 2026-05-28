# REPORT — Lateral fidelity ladder, Mach-E

- **Platform**: `FORD_MUSTANG_MACH_E_MK1` (Mach-E). Mach-E chosen because `yaw_rate_meas_rads` is the **measured** truth channel decoded from the openpilot Ford party DBC (Tesla rlogs do not decode this).
- **Operating contract**: `v` and `δ` are **clamped to measured** under the speed-known, lateral-only contract. Speed-state agreement is zero by construction and is not the metric here. Residuals are reported on `yaw_rate_pred − yaw_rate_meas`.
- **Data**: 8 Mach-E segments, 23,191 rows. Regime distribution: 21,264 straight / 1,559 steady / 368 transient. (Sample is straight-heavy; cornering numbers are noisier than the overall.)
- **Skills used**: composed `regime-segmentation` (load + tag) then `lateral-fidelity-triage` (variant ladder + sensor gate). Regime thresholds: `|δ|<0.01 rad` straight, `|dδ/dt|<0.05 rad/s` for steady vs. transient — identical in both skills.
- **Attribution scheme**: strict marginal, fixed order V0→V1→V2→V3→V4. Per-variant marginal = `RMSE(V_{i-1}) − RMSE(V_i)`. Sum of marginals equals total drop within numerical precision (well under the 15% guardrail).
- **Sensor gate** (`sensor.py out/best_V1.csv`): PASS sign-consistency (`corr(pred,meas)=0.997` on cornering) and PASS regression-check (`RMSE=0.01524 ≤ V0=0.01796`).

| Variant | Overall (mrad/s) | Straight | Steady | Transient | ΔOverall vs V0 |
|---|---:|---:|---:|---:|---:|
| V0  baseline (as-shipped) | 17.96 | 13.31 | 34.94 | 70.23 | +0.0% |
| V1  KS recalibrated + per-segment gyro bias | 15.24 | 7.20 | 37.10 | 76.17 | +15.2% |
| V2  Linear ST, prior C_α (286.6k / 355.9k) | 19.32 | 9.69 | 48.03 | 91.24 | −7.5% |
| V3  Linear ST, fit C_α (cf=150000, cr=150000) | 19.42 | 9.71 | 48.33 | 91.77 | −8.1% |
| V4  V3 + Ridge residual learner (LOO) | 27.55 | 12.95 | 71.28 | 128.92 | −53.4% |

## Marginal contribution per change

- **V1 → +2.73 mrad/s drop**. The only variant that improves on V0. Almost all of the gain lives in the **straight** regime (13.31 → 7.20 mrad/s, a 45.9% drop). Interpretation: V0 contains a per-segment yaw-gyro bias that V1 explicitly subtracts on straight-line samples. The canonical wheelbase `L=2.984 m` is the same as the shipped KS, so the gyro-bias term is doing the work.
- **V2 → −4.08 mrad/s** (regression). Adding the linear-ST gain term `1/(1 + K_us v²)` with the openpilot-canonical priors hurts because (a) cornering is only ~8% of rows here so V2's understeer-correction can't pay for itself, and (b) the priors are stiff (Cα_f=286.6k, Cα_r=355.9k); on this segment set they over-shrink the predicted yaw rate. Reported as a regression with cause, not buried.
- **V3 → −0.10 mrad/s** further (marginal worse than V2). The L-BFGS-B fit landed at the seed (1.5e5 / 1.5e5) — i.e. the optimiser made no useful move. Not pegged at the upper bound, so v0.5's `pegged-at-upper` flag does not fire; the symptom here is a non-converged fit rather than a saturated bound. The skill rule of "report regression with physical reason" applies: with only 1.9k cornering rows split across 8 segments, the C_α loss surface near the seed is flat enough that L-BFGS-B exits early.
- **V4 → −8.13 mrad/s** further (largest regression). Ridge on `[v, |a_y|, |δ|, sign(δ̇)]` trained leave-one-segment-out against V3's residuals **does not generalise across segments**: each segment's per-vehicle / per-route bias is large compared to the structure Ridge can latch onto, so OOF predictions add noise to V3 rather than removing it. Per the skill: "If V4 doesn't beat V3 out-of-fold, ship V3 and call V4 a regression. Partial > faked." Honoured — V4 flagged as a regression.

## Composition decision

`regime-segmentation` first (pure DataFrame transform: load_and_validate → tag), then `lateral-fidelity-triage` for the variant ladder. The two share the same regime thresholds by convention, so per-regime RMSE numbers in the variant table come directly from `segment.per_regime_rmse`, with `lateral-fidelity-triage` supplying every prediction column and the sensor gate.

## Best variant shipped

**V1** (KS with canonical L plus per-segment straight-line gyro-bias subtraction). Sensor PASS on both checks. V2/V3/V4 not shipped — flagged as regressions on this segment set.

## Limitations

- Sample is heavily straight-dominated (92% straight rows). Cornering RMSE values move on small row counts (368 transient rows total).
- The L-BFGS-B C_α fit did not converge away from its seed; a global search or larger cornering sample would be needed to know whether a re-tuned linear ST beats V1. Reported honestly rather than re-seeded post-hoc.
- Tesla segments deliberately excluded — they have no decoded `yaw_rate_meas_rads`.
- F-150 Lightning segments not run; would require a separate ladder and a low-`v` sub-step check (skill's v0.4 warning).
