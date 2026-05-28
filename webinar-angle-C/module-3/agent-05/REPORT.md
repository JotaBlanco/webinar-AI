# Module-3 / agent-05 (angle-C) — Lateral fidelity

## Headline

Per-platform `{bias b, static gain k, first-order lag τ}` correction on KS yaw-rate prediction. **Mach-E**: overall held-out test RMSE 0.01613 → 0.01534 rad/s (-4.9%); transient regime -15%. **F-150**: 0.02037 → 0.01614 rad/s (-20.8%); transient regime -15%.

## Platform, truth, contract

- Platforms: FORD_MUSTANG_MACH_E_MK1 (primary, 315 segs / 913 626 samp) and FORD_F_150_LIGHTNING_MK1 (230 segs / 667 141 samp). Tesla excluded (rule 4).
- Measured truth: `yaw_rate_meas_rads` from Ford CAN.
- `v_mps` and `delta_road_rad` are **clamped inputs**; lateral states are **predicted**. Speed-state agreement is zero by construction (rule 5).
- Residual convention: `pred − meas` (rule 1). Cornering `corr(δ_road, ψ̇_meas)` = +0.70 (Mach-E) → sign convention OK (rule 2).

## Variant ladder (strict-marginal V0→V3)

Per-platform fit (rule 8). Interleaved every-5th-sample train (rule 7); RMSE on held-out 4/5.

### FORD_MUSTANG_MACH_E_MK1 — yaw-rate test RMSE (rad/s)

| Variant | overall | straight | steady | transient |
|---|---|---|---|---|
| V0 baseline | 0.01613 | 0.00876 | 0.03180 | 0.05663 |
| V1 +bias `b=2.27e-4` | 0.01612 | 0.00875 | 0.03182 | 0.05665 |
| V2 +gain `k=1.069` | 0.01557 | 0.00947 | 0.02996 | 0.05052 |
| V3 +lag `τ=0.08 s` | 0.01534 | 0.00934 | 0.03003 | 0.04811 |

Marginals (overall): bias 1.6e-6, gain 5.6e-4, lag 2.3e-4. Sum 7.9e-4 = total V0→V3 drop (lossless).

### FORD_F_150_LIGHTNING_MK1 — yaw-rate test RMSE (rad/s)

| Variant | overall | straight | steady | transient |
|---|---|---|---|---|
| V0 baseline | 0.02037 | 0.00899 | 0.03614 | 0.05198 |
| V1 +bias `b=3.63e-3` | 0.02004 | 0.00800 | 0.03615 | 0.05195 |
| V2 +gain `k=0.860` | 0.01635 | 0.00638 | 0.02840 | 0.04536 |
| V3 +lag `τ=0.06 s` | 0.01614 | 0.00624 | 0.02842 | 0.04400 |

Marginals: bias 3.3e-4, gain 3.7e-3, lag 2.1e-4. Sum 4.2e-3 (lossless).

## Regressions flagged (with physical cause)

- **Mach-E V2 worsens straight regime** 0.00876 → 0.00947 (+8%). Cause: on near-straight segments ψ̇_pred is dominated by sensor/integrator noise; the 1.069 gain multiplies that noise. Fix-forward: apply gain only where `|δ_road| > threshold`, or fit a regime-aware gain.
- **Mach-E V4 a_y regresses** 0.338 → 0.363 m/s² (rule 9 coupled-consequence). Original `a_y_pred_mps2` column is not exactly `v·ψ̇_pred`; substituting the corrected ψ̇ exposes a constant pipeline offset.
- **F-150 `a_lat_meas_mps2` is suspect** — V0 a_y RMSE ~10.9 m/s² on straights, implausible. Flagged for separate decoding triage.

## Surprise

**The two Fords disagree on the sign of `k − 1`.** Mach-E `k = 1.069` (KS under-predicts ψ̇), F-150 `k = 0.860` (KS over-predicts ψ̇). A shared "Ford" gain would be wrong on both platforms in opposite directions. F-150 over-prediction is consistent with the heavier vehicle under-steering more than KS knows about (KS has no mass / cornering stiffness). Mach-E direction is the open puzzle — likely an effective-steer-ratio mis-cal at moderate g.

## Painful absence

The shared `code/` is read-only by contract, so the V2 gain and V3 lag live downstream of the KS integrator as a post-processor. Pushing them into the integrator (where they belong physically — gain = steer-ratio, lag = tire relaxation) requires a parameters.py change that this module is not allowed to make.

## Near-misses

- The bias term is meaningful on F-150 (1.6% of V0 overall) but a near-null on Mach-E. Resisted the temptation to drop it from the ladder — plan was locked.
- Considered refitting `b` after the lag. Did not — strict-marginal attribution requires fixed order.

## RPI artifacts

- `rpi/runs/20260527T140005Z/research.md`
- `rpi/runs/20260527T140005Z/plan.md`
- `rpi/runs/20260527T140005Z/implement-notes.md`

## Eval status

- `baseline_rmse.py` Mach-E + F-150 → matches V0 numbers.
- `schema_check.py out/FORD_MUSTANG_MACH_E_MK1__variant_sim.csv` → PASS
- `schema_check.py out/FORD_F_150_LIGHTNING_MK1__variant_sim.csv` → PASS

## Outputs

- `out/FORD_MUSTANG_MACH_E_MK1__ladder.json`, `out/FORD_MUSTANG_MACH_E_MK1__variant_sim.csv`
- `out/FORD_F_150_LIGHTNING_MK1__ladder.json`, `out/FORD_F_150_LIGHTNING_MK1__variant_sim.csv`
- `tools/fit_ladder.py`
