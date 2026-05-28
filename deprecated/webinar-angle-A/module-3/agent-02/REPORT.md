# Module-3 / agent-02 — Lateral-fidelity variant ladder (Mach-E)

## Setup

- Platform scored: **FORD_MUSTANG_MACH_E_MK1** (315 segments, 913 626 rows at 50 Hz).
- `yaw_rate_meas_rads` is the **measured** truth channel decoded from Ford CAN gyro — not a prediction, not a clamped self-consistency state.
- Operating contract: under `clamp_v_to_measured=True` and `clamp_delta_to_measured=True`, `v_mps` and `delta_road_rad` are **inputs (clamped)** at every step; `yaw_rate_pred_rads` and `a_y_pred_mps2` are the **predicted** lateral channels. Metric: `RMSE(yaw_rate_pred − yaw_rate_meas)` partitioned by regime.
- Regime mask (held constant, via `triage.regime_mask`):
  - straight: `|δ_road| < 0.01 rad`
  - steady cornering: `|δ_road| ≥ 0.01` ∧ `|dδ/dt| < 0.05 rad/s`
  - transient cornering: `|δ_road| ≥ 0.01` ∧ `|dδ/dt| ≥ 0.05 rad/s`
- Sign check: `corr(δ_road, ψ̇_meas) = +0.702` on cornering samples. Convention is correct.
- Attribution scheme: **strict marginal** in fixed order V0→V1→V2→V3→V4. Total V0→V4 drop = 0.00072; sum of marginals = 0.00071 (≈1.5% rounding gap, within 15% bar).

## Variant ladder

| Variant | Overall RMSE (rad/s) | Straight | Steady corner | Transient corner | Marginal drop (overall) |
|---|---:|---:|---:|---:|---:|
| V0 — baseline (`yaw_rate_resid_rads` as-is)                                    | 0.01613 | 0.00877 | 0.03173 | 0.05680 | — |
| V1 — KS recalibrated + per-segment straight-line yaw-gyro bias                  | 0.01469 | 0.00493 | 0.03168 | 0.05730 | -0.00143 |
| V2 — Linear ST, prior `C_α` (openpilot carParams) + same per-seg bias           | 0.01551 | 0.00339 | 0.03430 | 0.06277 | +0.00082 (regression) |
| V3 — Linear ST, fit `C_α` (bounded 5e4–5e5 N/rad) + same per-seg bias           | 0.01564 | 0.00349 | 0.03462 | 0.06307 | +0.00013 (regression) |
| V4 — Ridge residual learner on V3 residuals, leave-one-segment-out CV           | 0.01541 | 0.00357 | 0.03414 | 0.06179 | -0.00023 |

## Discussion

- **V1 carries the whole improvement.** Stock `yaw_rate_pred_rads` already uses canonical `L = 2.984 m` (max recompute diff = 3e-6 rad/s); the V1 lift is entirely **per-segment yaw-gyro bias subtraction** (mean 0.0007 rad/s, std 0.0070, range [-0.024, +0.019]). Cuts straight-regime RMSE almost in half (0.00877 → 0.00493).
- **V2 is a regression on this fleet — physical cause.** Linear ST with openpilot's prior `C_αf=286 551, C_αr=355 912 N/rad` makes steady and transient cornering RMSE worse (0.03430 vs 0.03168; 0.06277 vs 0.05730). The ST prior is *stiffer* than the Mach-E tyres want, so it under-predicts the gain shrinkage at high `|a_y|` — exactly the regression the variant catalogue calls out. KS, having no slip, accidentally matches better.
- **V3 confirms the prior is the problem, not the solver.** Default L-BFGS-B from `triage.fit_c_alpha` lands at `(1.5e5, 1.5e5)` (its init) with loss flat there. A multi-start grid finds the true minimum **pegged at the upper bound (5e5, 5e5) N/rad** — the fitter wants ST as stiff as possible, degenerate toward KS-like behaviour. The ST functional form simply does not fit these data. Reported as regression.
- **V4 is a marginal recovery.** Ridge on `[v, |a_y|, |δ|, sign(δ̇)]` with LOO CV claws back 0.00023 rad/s OOF against V3 — real, but smaller than V1's win and not enough to recover even V1's level. Honestly, **V1 is the variant to ship**.

## Recommendation

Ship **V1**. The ST upgrade does *not* improve lateral fidelity on this Mach-E fleet at the openpilot prior, and the in-bounds fit is degenerate. The bias subtraction in V1 is the only honest improvement available with the components in this harness.

## Limitations

- No non-linear ST / Pacejka rung available — V3's pegging suggests the slip-stiffness *relationship* is what needs to change, not the magnitudes of `C_α`. Harness offers no rung for that.
- No `evals/` directory in this module — could not auto-validate the report.

Files: `out/ladder_results.json`, `out/ladder_summary.txt`, `out/v1_bias_per_segment.json`, `tools/run_ladder.py`.
