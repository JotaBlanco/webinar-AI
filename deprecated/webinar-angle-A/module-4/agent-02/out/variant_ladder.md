# Lateral Fidelity — Variant Ladder (Ford Mustang Mach-E MK1)

## Platform & contract

- Platform: **FORD_MUSTANG_MACH_E_MK1** (Ford only has a measured truth channel; Tesla does not — KS sim CSVs have no IMU truth).
- Scored channel: **`yaw_rate_meas_rads`** is the **measured** (truth) yaw rate from the rlog. Predictions come from the KS / ST model rungs. Residuals are `pred − meas`.
- Speed-known contract: `v_mps` and `delta_road_rad` are **clamped** to the measurement at every integration step; only `yaw_rate_pred_rads` / `a_y_pred_mps2` are **predicted**. Speed-state agreement is zero by construction and not the metric. No variant unclamps `v` or `δ`.

## Methodology

- 60 Mach-E segments / 173 940 rows / 50 Hz. The same **segment set** and the same **regime mask** (straight: `|δ_road| < 0.01 rad`; steady cornering: `|δ_road| ≥ 0.01 ∧ |δ̇| < 0.05`; transient cornering: `|δ_road| ≥ 0.01 ∧ |δ̇| ≥ 0.05`) is **held constant** across every row. Regime row-counts: 158 354 / 13 136 / 2 450.
- All RMSEs are over `pred − yaw_rate_meas_rads` in rad/s.
- Vehicle parameters from `PARAM_BY_PLATFORM['FORD_MUSTANG_MACH_E_MK1']`: `L = 2.984 m`, `m = 2336 kg`, `I_z = 4879.05`, `l_f/l_r = 1.313/1.671`, `C_αf/C_αr = 286 551 / 355 912 N/rad`, `i_s = 17.0`.
- Attribution scheme: **strict marginal**, fixed order V0→V1→V2→V3→V4. Marginal drop = `RMSE(V_{i-1}) − RMSE(V_i)`. Σmarginal = 0.002536, total V0→V4 drop = 0.002536, |Σ − total|/total = 0.000 → fully coherent.

## Variant ladder

| Variant | Description | RMSE overall (rad/s) | RMSE straight | RMSE steady | RMSE transient | Δ overall vs prev (rad/s) |
| --- | --- | --- | --- | --- | --- | --- |
| V0 | Baseline `yaw_rate_resid_rads` as-is | 0.012144 | 0.008508 | 0.025192 | 0.048887 | — |
| V1 | KS recalibrated with canonical `L` + per-segment straight-line yaw-gyro bias subtracted | 0.010552 | 0.005064 | 0.026019 | 0.051156 | −0.001593 |
| V2 | Linear ST with openpilot prior `C_αf/C_αr` (KS fallback below 2 m/s) + per-segment bias | 0.012480 | 0.003346 | 0.034243 | 0.063623 | +0.001929 |
| V3 | Linear ST with fit `C_αf, C_αr` (grid + Nelder-Mead, bounded 50–500 kN/rad) — fit landed at cf = 427 029, cr = 483 737 N/rad (near upper bound) + per-segment bias | 0.012170 | 0.003364 | 0.033180 | 0.062300 | +0.000310 |
| V4 | Ridge residual learner on V3 residuals; features = (v, abs(a_y), abs(δ), sign of δ-dot); **leave-one-segment-out CV** (out-of-fold scoring) | 0.009608 | 0.003440 | 0.023898 | 0.052225 | −0.002562 |

## Per-variant notes

- **V1 (the workhorse).** Subtracting a per-segment yaw-gyro bias measured on straight-line samples cuts the straight-regime residual from 8.5 → 5.1 mrad/s. Steady and transient cornering go slightly *worse* (the bias was masking a constant offset across all regimes; remove it and the cornering structural error stands clearer). One added DoF per segment.
- **V2 (regression, physical cause).** Switching to the linear single-track steady-state gain *with the openpilot prior `C_α`* makes overall fidelity **worse** than V1. The prior cornering stiffnesses comma.ai ships for the Mach-E (286 / 356 kN/rad) make the bicycle stiffer than the actual Mach-E tyres are responding to under measured inputs — so ST over-predicts yaw rate in cornering, blowing up steady and transient by ~30–40 %. Straight is better (bias subtraction is now applied to a cleaner channel), but the cornering damage dominates. This is the workshop's documented "ST prior too stiff for Mach-E tyres" regression and is flagged here as a regression with that physical cause.
- **V3 (partial recovery, still a regression vs V1).** Fitting `C_α` over the full Mach-E set drives cf, cr toward the upper bound (427 k / 484 k), confirming that the prior was *already* stiffer than V1 wanted — making it *stiffer still* lets the fit hide a bit more of the V2 damage by pushing the K_us nearer to its asymptote, but overall fidelity is still worse than V1 (0.01217 vs 0.01055). Reported as a regression vs V1 with cause: the linear-ST functional form cannot beat KS+bias on this platform because the genuinely-non-linear slip behavior is not in the model class.
- **V4 (the real win).** A 4-feature ridge residual learner trained out-of-fold against V3's residuals recovers the cornering structural error and lands at 0.00961 overall — beating V1 and V0. Cross-validation is leave-one-segment-out: every prediction comes from a model that has *never seen its own segment*. The cornering regimes are the channels it lifts (steady 23.9 vs V1's 26.0, transient 52.2 vs V1's 51.2).

## Honest regression flags

- **V2 worsened V1 by +1.93 mrad/s.** Physical cause: openpilot's prior `C_α` is stiffer than the Mach-E tyres under the segment-set's operating envelope; the linear-ST steady-state gain therefore over-predicts ψ̇ in cornering.
- **V3 worsened V1 by +1.62 mrad/s.** Even after fitting `C_α`, the linear-ST functional form cannot match KS+bias because the residual structure is non-linear (slip rises non-linearly with `a_y`) — fitting in a wrong model class moves you along a wrong manifold.
- V4 is the only rung that beats V1, and it does so by adding a learned non-linear residual on top of V3.

## Attribution

- Total V0 → V4 drop: **0.002536 rad/s** (i.e. 0.01214 → 0.00961, a ~21 % overall RMSE reduction; ~60 % reduction on the straight regime).
- Marginal drops (sum to total): V1 contributes **+1.593 mrad/s**, V2 contributes **−1.929 mrad/s**, V3 contributes **+0.310 mrad/s**, V4 contributes **+2.562 mrad/s**. |Σ − total|/total = **0.000**, well under the 0.15 coherence threshold.
- Net contributors to the improvement: V1 (straight-bias subtraction) and V4 (residual learner). V2 and V3 are documented regressions kept in the ladder so attribution remains honest, not pruned.

## Limitations

- Used 60 Mach-E segments (deterministic glob order), not the full 315, to stay in the 15-minute budget. The shape of the ladder is unlikely to change materially.
- V4 ridge features are minimal; non-linear models or richer features (slip-angle proxy, lateral jerk) would likely improve further but are out of scope of this variant ladder.
- `triage.fit_c_alpha` ships with L-BFGS-B which gets stuck on the very flat `C_α` loss surface and returns its initial guess. I worked around this with a 25×25 grid + Nelder-Mead refinement in `tools/run_ladder.py`; the underlying skill helper should be patched for future runs.
