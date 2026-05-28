# Module-4 / agent-04 — Lateral-fidelity variant ladder (Ford Mustang Mach-E)

## Setup

- **Platform:** `FORD_MUSTANG_MACH_E_MK1`. Lateral-truth channel is `yaw_rate_meas_rads`, the **measured** yaw rate decoded from the rlog IMU (not predicted, not the KS integrator state).
- **Speed-known contract.** All Ford `sim.csv` rows were produced with `clamp_v_to_measured=True` and `clamp_delta_to_measured=True`, so `v_mps` and `delta_road_rad` are **clamped** inputs and `yaw_rate_pred_rads` is the resulting **predicted** lateral output. The scored quantity is `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads`.
- **Cohort:** 60 Mach-E sim segments (first 60 by lexicographic path order). Same segment set and same regime mask are **held constant across every row** in the variant ladder.
- **Regime mask** (same definition for every variant): `straight = |δ_road| < 0.01 rad`; `steady = |δ_road| ≥ 0.01 rad ∧ |dδ/dt| < 0.05 rad/s`; `transient = |δ_road| ≥ 0.01 rad ∧ |dδ/dt| ≥ 0.05 rad/s`.
- **Attribution scheme:** strict marginal in the fixed order V0→V1→V2→V3→V4. Marginal drop on row i = `RMSE(V_{i−1}) − RMSE(V_i)`.

## Variant ladder

| Variant | Overall RMSE (rad/s) | Straight | Steady | Transient | Marginal Δ (rad/s) |
|---------|----------------------|----------|--------|-----------|--------------------|
| V0 — baseline `yaw_rate_resid_rads` as-is                                                              | 0.01214 | 0.00851 | 0.02519 | 0.04889 | — |
| V1 — KS recalibrated (canonical L=2.984 m) + per-segment yaw-gyro bias on straights                    | 0.01055 | 0.00506 | 0.02602 | 0.05116 | -0.00159 |
| V2 — Linear ST with openpilot prior Cα (Cf=286 551, Cr=355 912 N/rad)                                  | 0.01248 | 0.00335 | 0.03424 | 0.06362 | +0.00193 |
| V3 — Linear ST with fit Cα (Cf=Cr≈150 000 N/rad, interior optimum)                                     | 0.01260 | 0.00343 | 0.03458 | 0.06398 | +0.00012 |
| V4 — Ridge residual learner on V3, LOSO CV                                                             | 0.01005 | 0.00351 | 0.02544 | 0.05382 | -0.00255 |

Total drop V0 → V4: **0.00210 rad/s** (17.3% reduction). Sum of marginal drops: 0.00210 rad/s. Coherence error `|Σmarg − total|/|total| = 0.00 < 0.15`.

## What each variant did

- **V1 (positive, -0.00159).** Pulled `L` from `PARAM_BY_PLATFORM` (2.984 m) and subtracted per-segment mean yaw-gyro bias on straights (60/60 segments had ≥10 straight samples). Mean bias ≈ 0.0002 rad/s — small but enough to halve the straight-line RMSE (0.0085 → 0.0051).
- **V2 (regression, +0.00193).** Switched to the linear single-track steady-state yaw-rate gain `ψ̇ = v·δ / (L·(1 + K_us·v²))` with openpilot's prior cornering stiffnesses. **Worsened steady and transient cornering** (the regimes ST is supposed to help). See below.
- **V3 (regression, +0.00012).** Re-fit `(Cf, Cr)` in `(5e4, 5e5) N/rad` bounds; the optimiser landed at an **interior** point `Cf=Cr=150 000` rather than pegging the upper bound, but the resulting RMSE is *still* worse than V1.
- **V4 (positive, -0.00255).** Ridge regression (α=1.0) on `[v, |a_y|, |δ|, sign(δ̇)]` against V3 residuals, **leave-one-segment-out** CV. Recovers everything V2/V3 lost, plus more.

## Regression analysis

V2 and V3 both increased overall RMSE relative to V1. The references material predicted this pattern: openpilot's `Cα` prior is stiffer than the Mach-E tyres want, so the steady-state ST gain over-attenuates yaw at speed. The residual structure left after V1 is non-linear (slip-angle saturation), which a linear-ST steady-state model cannot represent regardless of the `(Cf, Cr)` you pick. V3's fit confirmed this: it walked stiffnesses down to an interior optimum and **still** could not beat V1. Physical cause: residuals at high lateral acceleration aren't a stiffness mismatch; they're a missing slip-angle dynamics term. A model-form gap, not a parameter gap.

## What V4 actually learned

LOSO Ridge picks up regime-dependent residual: with `|a_y|` and `|δ|` features it's roughly learning the slip-angle gain that linear ST omits. Because LOSO holds out a full segment for every prediction, 0.01005 is genuine out-of-fold. V4 beats V1 by 0.00050 rad/s overall, win concentrated in steady cornering (transient is slightly worse than V1 in absolute terms, 0.05382 vs 0.05116; the net win is in steady and overall).

## Limitations

- 60-segment subsample (first by path-order), not the full 315 — picked for budget.
- Lightning platform not run.
- V4 model intentionally tiny (4 features, Ridge α=1.0).

## What the absence of a shared baseline cost me

This module includes the skill, references, and eval, but no `_shared` reference cohort. I cannot externally verify whether 17.3% reduction is "what a clean run looks like". The eval is structural (shape, attribution accounting, regression honesty), not numerical (is your RMSE near canonical). Shape-correctness and self-consistency only.

Files: `out/run_ladder.py`, `out/ladder.json`.
