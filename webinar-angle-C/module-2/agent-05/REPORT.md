# Module-2 / agent-05 (angle-C) — Lateral fidelity

## Platform & truth

Scored on **FORD_MUSTANG_MACH_E_MK1** (315 segments). `yaw_rate_meas_rads` is the measured truth channel decoded from the rlog IMU; Tesla excluded per AGENTS.md rule 4 (no decodable yaw-rate truth).

ISO 8855 sanity: `corr(delta_road, yaw_rate_meas)` on cornering = **+0.790** (expected positive).

## Operating contract

`v` and `δ` are **clamped to measured**, not predicted. Only lateral states (ψ, ψ̇, a_y) are under test.

## Variant ladder

Per-platform fit, interleaved 5-way split, test-only RMSE of yaw-rate residual (rad/s):

| Variant | all | straight | steady-corner | transient-corner |
|---|---:|---:|---:|---:|
| V0 baseline (`yaw_rate_resid_rads` as-is) | 0.01613 | 0.00820 | 0.03100 | 0.04832 |
| V1 bias removal (b = +0.00075 rad/s) | 0.01614 | 0.00817 | 0.03170 | 0.04694 |
| V2 steer-gain k = 1.0843 | **0.01561** | 0.00881 | 0.03107 | **0.04005** |
| V3 lag align (+40 ms) | 0.01624 | 0.00905 | 0.03173 | 0.04393 |

Fit discipline: all variants are **per-platform**, fit on the train fold (4/5 of samples, interleaved), reported on the held-out test fold. Same segment set, same regime masks across rows (straight: |ψ̇|<0.03; transient: cornering with |dψ̇/dt|≥0.10).

## Strict marginal accounting (V0 → V_last, "all" RMSE)

- V1 bias removal: Δ = -0.08% (bias is ~0; ISO sign already correct upstream).
- V2 steer-gain: Δ = +3.29% improvement (transient-corner RMSE drops 17%: 0.0483 → 0.0401).
- V3 lag align: Δ = -3.92% (regression).
- Net V0 → V3: -0.72% overall. V2 alone delivers +3.3% net.

## Regressions (with physical cause)

- **V3 lag-align (+40 ms) regresses.** Cause: Mach-E KS prediction is in-phase with measured ψ̇ once V2's gain correction is applied; the residual transient-cornering error is amplitude, not timing. Shifting by ±2 samples decorrelates steady-state cornering peaks more than it aligns transients. The minimiser on the cornering subset picked +40 ms; on **all** samples it hurts straight-line noise.
- **V1 bias is effectively zero** (+0.75 mrad/s ≈ 0.04 deg/s). The Ford IMU is well-zeroed; bias removal is a no-op on this platform.

## Coupled `a_y` note

`a_y_pred = v · ψ̇`. Any operational use of V2 must re-derive `a_y_pred_mps2 = v·(k·ψ̇_v1)` and recompute `a_y_resid_mps2`. Not re-scored here; V2 propagates to a_y by the same +8.4% gain on ψ̇.

## Painful absence

No per-segment IMU offset table to test rule 8's "calibration vs improvement" distinction — per-platform fit is the only honest framing.

## Near-misses

Lag alignment looked promising on cornering-only train subset (best_lag=+40 ms, lower train RMSE) but failed out-of-fold — classic over-fit to autocorrelated cornering peaks (rule 7 trap, almost re-paid).

## Surprise

Bias is genuinely zero on Mach-E. Dominant error is a **steering-gain under-prediction of ~8%** — KS with openpilot-canonical i_s=17.0 systematically under-rotates the Mach-E in transient cornering. Either i_s is closer to 15.7 in practice, or compliance steer (tire/bushing) is adding ~8% effective δ at the road wheel that KS doesn't model.

Files: `tools/ladder.py`, `out/ladder.csv`.
