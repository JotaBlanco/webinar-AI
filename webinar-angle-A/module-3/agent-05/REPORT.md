# Module-3 / agent-05 — Lateral-fidelity triage (Mach-E)

## Setup

- Platform scored: **FORD_MUSTANG_MACH_E_MK1**. `yaw_rate_meas_rads` is the **measured** yaw-rate channel from the rlog IMU (not predicted, not self-consistency).
- Speed-known contract: `v_mps` and `delta_road_rad` are **clamped** to measured signals. The integrator's `v`/`δ` updates are overwritten every step. Only quantity under test is `yaw_rate_pred_rads`; residual = `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads`.
- Segment set: first 80 of 315 Mach-E `sim.csv` files (231 926 rows — 211k straight / 17.6k steady / 2.9k transient). Identical segment-set and identical regime mask for every row.
- Regime mask (`triage.regime_mask`): straight `|δ|<0.01`; steady `|δ|≥0.01 ∧ |dδ/dt|<0.05`; transient `|δ|≥0.01 ∧ |dδ/dt|≥0.05`.
- Parameters: openpilot-canonical from `PARAM_BY_PLATFORM` (L=2.984, l_f=1.313, l_r=1.671, m=2336, I_z=4879.05, Cαf_prior=286 551, Cαr_prior=355 912).

## Attribution scheme

- **Strict marginal**, fixed order V0→V1→V2→V3→V4. Total drop V0→V4 = **0.00227 rad/s**. Sum of marginals = **0.00228 rad/s** (closes to within 0.5%, well under 15%).

## Variant ladder (RMSE of yaw-rate residual, rad/s)

| Variant | Overall | Straight | Steady cornering | Transient cornering | Marginal Δ overall | Notes |
|---|---|---|---|---|---|---|
| V0 baseline (resid as-is)                | 0.01190 | 0.00853 | 0.02331 | 0.05219 | — | No preprocessing |
| V1 KS recal + per-seg yaw bias           | 0.01013 | 0.00498 | 0.02395 | 0.05406 | **-0.00177** | Bias from straight-line mean residual |
| V2 Linear ST, prior Cα                   | 0.01174 | 0.00365 | 0.03104 | 0.06482 | **+0.00161** (regression) | Straight improves but cornering RMSE rises ~30% |
| V3 Linear ST, fit Cα (Nelder-Mead)       | 0.01142 | 0.00361 | 0.02995 | 0.06352 | **-0.00033** | Cαf=312 267, Cαr=318 880 — not pegged |
| V4 Residual learner on V3 (LOO)          | 0.00963 | 0.00370 | 0.02355 | 0.05525 | **-0.00179** | Ridge on [v,|a_y|,|δ|,sign(δ̇)], LOSO |

**Headline:** total drop = 19% relative (0.00227 rad/s absolute); V0 0.01190 → V4 0.00963.

## Per-variant commentary

- **V1 — KS recalibrated.** Canonical L=2.984 m and subtract per-segment straight-line yaw-gyro bias. Straight-regime RMSE halves (0.0085 → 0.0050). Cornering regimes nudge up because V0 included offsetting biases that V1 removes.
- **V2 — Linear ST with prior Cα.** *Regression.* Openpilot-canonical Cα prior is too stiff for these tyres: steady-state gain `v·δ/(L·(1+K_us·v²))` under-predicts yaw rate at moderate-to-high `|a_y|`, blowing up steady and transient regimes by ~30%. Straight regime improves only marginally (dominant straight-line term is bias, not slip).
- **V3 — Linear ST with fit Cα.** Methodology note: skill helper `triage.fit_c_alpha` uses L-BFGS-B with default finite-difference step, which produces a numerically-zero gradient at the ~1e5 parameter scale and never moves off `x0`. Re-fit with Nelder-Mead (no gradient) in `out/run_ladder.py`, bounded to (5e4, 5e5). Optimum: Cαf=312 267, Cαr=318 880 N/rad — neither bound pegged, but only 0.00033 rad/s marginal gain. Confirms ST steady-state form is structurally limited for transient cornering (no tyre relaxation lag, no slip-angle dynamics).
- **V4 — Residual learner.** Small Ridge regressor (α=1) on `[v, |a_y|, |δ|, sign(δ̇)]` against V3 residuals, leave-one-segment-out. OOF RMSE improves to 0.00963 — best overall and the only variant that improves transient cornering relative to V3 (0.0635 → 0.0552). The model is learning unmodelled slip and steering-rate-dependent lag.

## Regressions explicitly flagged

- **V2 (Linear ST prior)** — overall regression (-0.00161 rad/s). Physical cause: openpilot prior tyre stiffness for the Mach-E is too high for the actual rubber/load combination, so the steady-state gain predicts a smaller yaw rate than measured, biasing all cornering samples positive in residual.

## Recommendation

Ship **V1 + V4** as the production stack:
1. KS with canonical L and per-segment yaw-bias correction (V1).
2. Linear ST with fit Cα (V3) as the cornering substrate.
3. LOO-validated residual learner (V4) on top, fed `[v, |a_y|, |δ|, sign(δ̇)]`.

The ST stage carries its weight only because the residual learner can clean up after it; without V4, V1 alone would beat V2/V3 on overall RMSE.

## Methodological finding

The skill's helper `triage.fit_c_alpha` is broken in a *silent* way on this dataset: L-BFGS-B with default `eps≈1.5e-8` produces zero finite-difference gradient when parameters are O(1e5), so it returns `x0` unchanged and reports `pegged=False`. The "if it pegs at the upper bound, flag it" guard would never fire — but the fit is still degenerate. A procedure's failure mode can be invisible to the procedure's own self-check.

Files: `out/run_ladder.py`, `out/ladder_results.json`.
