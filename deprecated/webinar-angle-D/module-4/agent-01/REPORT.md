# REPORT.md — lateral-fidelity triage, module-4 / agent-01

- **Platform:** `FORD_MUSTANG_MACH_E_MK1` (Mach-E MK1). `yaw_rate_meas_rads` is **measured truth** decoded from the openpilot rlog IMU; not a derived channel.
- **Contract:** speed-known, lateral-only. `v_mps` and `delta_road_rad` are **clamped to measured** at each KS step (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Speed-state agreement is zero by construction and is not in scope.
- **Residual under test:** `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads`.
- **Segment set:** 12 Mach-E segments, 34 860 rows. Regime counts: 29 907 straight / 4 148 steady cornering / 805 transient cornering.
- **Skills composed:** `regime-segmentation` (tags `regime` column from `δ`, `dδ/dt`) → `lateral-fidelity-triage` (variant ladder). Lockstep check `triage.regime_mask` vs `segment.tag` = 1.0000 agreement.
- **Attribution scheme:** strict marginal, fixed order V0→V1→V2→V3→V4. Sum of marginals = 0.00042 rad/s = total drop V0→V4 (within 15 % — telescoping holds, no overlap).
- **Sensor gate:** PASSED on best variant V1. `corr(pred, meas)` on cornering = 0.997 (> 0). `RMSE(V1) = 0.00885 ≤ RMSE(V0) = 0.01082`.

## Variant ladder

| Variant | Overall RMSE (rad/s) | Straight | Steady cornering | Transient cornering | Marginal Δ vs prev | Verdict |
|---------|---------------------:|---------:|-----------------:|--------------------:|-------------------:|---------|
| V0 — pre-computed residual, no preprocessing | 0.01082 | 0.00803 | 0.01774 | 0.03242 | — | baseline |
| V1 — KS recalibrated + per-segment straight-line yaw-gyro de-bias | **0.00885** | 0.00365 | 0.01796 | 0.03516 | **−0.00197** | **best, ship** |
| V2 — Linear ST, prior Cα (openpilot-canonical Mach-E values) | 0.01028 | 0.00318 | 0.02193 | 0.04144 | +0.00142 | **regression vs V1** — prior stiffness over-rotates this dataset on cornering |
| V3 — Linear ST, fit Cα (grid search, bounds 5e4–5e5 N/rad) — `C_αf=334 295`, `C_αr=318 109`, not pegged | 0.00951 | 0.00300 | 0.02010 | 0.03877 | −0.00076 | partial recovery vs V2, still **regression vs V1** |
| V4 — Ridge residual learner on V3 residuals, leave-one-segment-out CV | 0.01040 | 0.00344 | 0.02359 | 0.03710 | +0.00089 | **regression** — OOF RMSE = 0.01040 > V3, does not generalise; shipped as V3 not V4 per skill rule |

## Per-variant notes

- **V1.** All gain is in the straight regime (0.00803 → 0.00365 rad/s). Cornering regimes worsen slightly because the constant per-segment bias is removed uniformly while cornering residuals are not bias-dominated. Honest physical reading: this is a gyro-bias correction, not a model-fidelity upgrade.
- **V2.** ST with the openpilot-canonical prior Cα makes straights marginally better (0.00318) but trades it back two-fold in steady and transient cornering. Cause: the prior Cα is calibrated for openpilot's lane-keeping operating point, which is stiffer than this set of segments needs; ST then under-predicts steady cornering yaw rate.
- **V3.** Grid-search fit lands at `C_αf=334 295`, `C_αr=318 109` N/rad — *not* pegged at the 5e5 upper bound, so v0.5's pegged-Cα warning does not fire. Helper limitation: `triage.fit_c_alpha`'s default `L-BFGS-B` step is below O(1e5) numerical resolution and returns `x0` unchanged. The grid-search wrapper in `tools/run_ladder.py` replaces it. Methodology is unchanged; the helper deserves a future patch.
- **V4.** Ridge on `[v, |a_y|, |δ|, sign(δ̇)]` against V3 residuals. LOO OOF RMSE (0.01040) > V3 (0.00951), so by the skill's own rule, V4 is a regression and we ship V3-as-floor, V1-as-best. The learner has no generalisable signal at this segment count.

## Headline findings

- Best variant V1, overall RMSE 0.00885 rad/s, an 18.2 % drop vs V0.
- The win is a **straight-line gyro-bias artefact**, not a tyre/stiffness modelling improvement. Cornering RMSE actually *worsens slightly* under V1.
- More physics (V2, V3) hurts on this Mach-E subset; openpilot's prior Cα is too stiff for these segments, and even fit Cα doesn't claw back the cornering regressions vs V1.
- The Ridge residual learner (V4) does not generalise out-of-fold — shipped as V3 floor, not V4.
- Sum of strict-marginal drops V0→V4 = 0.00042 = total drop V0→V4 (exact telescope, well within 15 % tolerance).

## Composition and limitations

- Composed `regime-segmentation` upstream of `lateral-fidelity-triage`. The regime-tagged DataFrame fed every per-regime RMSE column. Both skills share thresholds (`|δ|<0.01`, `|dδ/dt|<0.05`) — verified 1.0000 lockstep agreement at runtime.
- Limitations / declared scope: only 12 Mach-E segments used (315 available); no Lightning segments used (Lightning's stationary stretches would stress the v_min ST fallback differently). `fit_c_alpha` helper bug worked around with a grid search.
- Sensor gate: PASSED.
