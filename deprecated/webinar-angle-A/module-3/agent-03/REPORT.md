# Module-3 / agent-03 — Lateral fidelity variant ladder (Mach-E)

## Scope and contract

- Platform: **FORD_MUSTANG_MACH_E_MK1** (315 segments, 913 626 rows at 50 Hz).
- `yaw_rate_meas_rads` is the **measured** Ford CAN/IMU truth channel — not a prediction, not a self-consistency replay.
- Under the speed-known lateral-only contract, `v_mps` and `delta_road_rad` are **clamped** to measurement at every integrator step; the **predicted** quantity under test is `yaw_rate_pred_rads`.
- Residual scored: `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads`.
- Regime mask (held constant): straight `|δ|<0.01`, steady `|δ|≥0.01 ∧ |dδ/dt|<0.05`, transient `|δ|≥0.01 ∧ |dδ/dt|≥0.05`. Counts: 785 093 / 106 978 / 21 555.
- Sign sanity: `corr(δ, ψ̇_meas) = +0.690` — left-positive convention confirmed.

## Variant ladder (yaw-rate RMSE in rad/s)

| Variant | Description | Overall | Straight | Steady | Transient | Marginal Δ overall |
|---|---|---:|---:|---:|---:|---:|
| V0 | Stock `yaw_rate_resid_rads` as-is                                                       | 0.01613 | 0.00877 | 0.03173 | 0.05680 | — |
| V1 | KS recalibrated (canonical L) + per-segment yaw-gyro bias on straights                  | 0.01469 | 0.00493 | 0.03168 | 0.05730 | **-0.00144** |
| V2 | Linear ST steady-state with prior `C_α` (286.6k / 355.9k)                                | 0.01551 | 0.00339 | 0.03430 | 0.06277 | **+0.00082** (regression) |
| V3 | Linear ST with fit `C_α` (L-BFGS-B + DE cross-check; best ≈ 362k / 369k)                | 0.01564 | 0.00349 | 0.03462 | 0.06307 | **+0.00013** (regression) |
| V4 | Ridge residual learner on `[v, |a_y|, |δ|, sign(δ̇)]`, LOO OOF                           | 0.01541 | 0.00357 | 0.03414 | 0.06179 | **-0.00023** |

## Attribution

- **Strict marginal**, fixed order V0→V1→V2→V3→V4. Sum of marginals: `-0.00144 + 0.00082 + 0.00013 - 0.00023 = -0.00072`. Total V0→V4: `0.01613 - 0.01541 = 0.00072`. **Match exact** (<1% of total drop, well under 15% guard).

## What actually moved the needle

- **V1 carries the whole improvement.** Stock `yaw_rate_pred_rads` already uses canonical `L = 2.984 m` (max recompute diff = 3e-6 rad/s) — there is no L-error to fix. V1's lift is entirely **per-segment yaw-gyro bias subtraction**: 311 of 315 segments had ≥5 straight samples; bias mean 0.0007 rad/s, std 0.0070 rad/s, range [-0.024, +0.019]. Removing those static offsets cuts the straight-regime RMSE almost in half (0.00877 → 0.00493).
- **Steady and transient regimes barely move under V1**, because gyro bias is a constant offset and the steady/transient residuals are dominated by un-modelled slip, not bias.
- **V2 and V3 are regressions.** Physical cause: openpilot's prior cornering stiffnesses (286.6k front / 355.9k rear) characterise a stiffer-than-reality tyre, so `K_us` magnitude is too small (slight oversteer/near-neutral) — at moderate `v` the ST yaw-rate gain ends up *larger* than reality, overshooting `ψ̇_meas`. The DE fit (which dodges the L-BFGS-B local-minimum trap at x0) settles at ≈ (362k, 369k) — even higher Cα than the prior — confirming the loss surface wants *more* stiffness, i.e. closing the wrong gap. The actual gap is non-linear slip and tyre relaxation length, which a linear ST cannot represent.
- **V4 (residual learner LOO) recovers most of V3's regression** but cannot beat V1. With OOF RMSE 0.01541, the learner finds modest structure in `[v, |a_y|, |δ|, sign(δ̇)]` against the V3 residual, but it's repairing damage V2/V3 caused. **Honest finish is to ship V1.**

## Headline result

- Best lateral yaw-rate RMSE: **V1 = 0.01469 rad/s** (vs V0 = 0.01613 rad/s, an **8.9% reduction**).
- All of that gain is attributable to **per-segment yaw-gyro bias subtraction**, computed from straight-line samples only.
- The ladder is honest about V2/V3 being regressions.

## Limitations

- The `a_y` channel used in the residual learner is `a_y_pred_mps2` (predicted), not `a_lat_meas_mps2`. Using the measured channel might add genuine slip-onset information; unexplored.
- Bias subtraction is per-segment; a device-level bias estimator would generalise better but was out of scope.
- No non-linear or dynamic ST (Pacejka, relaxation length) — references explicitly bound the ladder to KS → linear-ST → residual learner.

Files: `out/ladder_summary.json`, `tools/run_ladder.py`.
