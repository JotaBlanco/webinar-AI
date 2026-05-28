# Module-4 / agent-03 (angle-B) — Lateral fidelity

## Headline

Only one variant of four improved on KS; the rest regressed. On 80 Ford Mach-E segments (203 303 samples, v ≥ 2 m/s), overall yaw-rate-residual RMSE went 0.01451 → 0.01262 rad/s with **per-segment IMU yaw-gyro bias removal (V1, -13%)**, and got worse with every cornering-model upgrade attempted.

## Stated platform & contract

- Platform: `FORD_MUSTANG_MACH_E_MK1` (Tesla excluded — no truth channel).
- Clamped inputs: `v_mps`, `delta_road_rad`. Predicted output: `yaw_rate_pred_rads`. Residual under test: `yaw_rate_resid_rads` (pred − meas).
- Sign sanity: `corr(δ_road, ψ̇_meas) = +0.934` on corners (positive → OK).

## Variant ladder, per-regime RMSE (rad/s), strict marginal accounting in fixed order

| Variant | overall | straight | steady | transient | marginal |
|---|---|---|---|---|---|
| V0 baseline | 0.01451 | 0.00890 | 0.02706 | 0.04893 | — |
| V1 IMU yaw-gyro bias / seg | 0.01262 | 0.00474 | 0.02673 | 0.04884 | **-0.00189** |
| V2 lin-ST steady, prior C_α | 0.02035 | 0.01415 | 0.03652 | 0.06065 | **+0.00773** (regression) |
| V3 lin-ST steady, fit C_α LOSO | 0.02188 | 0.01787 | 0.03360 | 0.05538 | **+0.00153** (regression) |
| V4 Ridge residual LOSO | 0.02143 | 0.01836 | 0.03004 | 0.05168 | -0.00045 |

Total V0→V4 = +0.00692 (worse). Sum of marginals = total exactly. Attribution: **strict marginal in fixed lock-step V0→V4** — each row's marginal is attributed to the rung that added the DoF.

## Painful absence

KS is not the lateral-fidelity bottleneck on this dataset — IMU yaw-gyro offset is. The variant the fidelity ladder treats as "cheapest" (per-segment bias) is the only one that delivered. The classical KS → linear-ST upgrade regressed. The honest path forward is **linear-ST dynamic (not steady-state)** or non-linear tyre; the steady-state gain rung does not earn its keep on this car.

## Near-misses (regression flags, honestly logged)

- V2 (prior C_α) over-states understeer for the Mach-E vs the openpilot prior; SS-ST yaw rate is ~30% short.
- V3 LOSO fit inverted the C_αf/C_αr ratio (median 394k / 257k vs prior 287k / 356k) and clustered C_αf at 392–400k — upper-physical band. Per skill: this is the regression flag that says **the linear-ST steady-state form is misspecified**, not just its priors.
- V4 (Ridge LOSO) reclaimed 0.00045 of V3's 0.00926 regression — linear residual learner cannot launder a misspecified steady-state baseline.

## Surprise

The straight regime, not the cornering regime, contains the dominant fix. KS is geometric and predicts ~0 yaw rate on straights; any non-zero straight-regime residual is necessarily sensor bias, not model gap. That 13% overall RMSE drop is essentially free.

## RPI artifacts

- Research: `rpi/runs/20260527-155852/research.md`
- Plan (locked): `rpi/runs/20260527-155852/plan.md`
- Implement notes: `rpi/runs/20260527-155852/implement-notes.md`
- Code: `tools/run_ladder.py`. Output: `out/ladder.csv`.
