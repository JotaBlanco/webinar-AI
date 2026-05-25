# Plan — improvements to evaluate

> Phase 2. Read only research.md. No code yet.

## Candidate improvements (4 — pick 2)

### Candidate A — Per-platform constant yaw-rate bias correction
- **Hypothesis (physical):** A non-zero pooled `mean(yaw_rate_resid)` implies an upstream calibration offset (IMU zero-rate, wheelbase miscalibration, or frame-convention slip) that produces a constant component in the residual. Removing it is a "free RMSE" win iff the residual is bias + noise.
- **Signal that suggests it:** Mach-E pooled mean +0.32 °/s; F-150 pooled mean −0.87 °/s. Both large vs noise std.
- **How to implement:** `skills/yaw-bias-correction/apply.py` already exists. Run it from baseline CSVs to `out/sim_+biasA/`. The script adds the per-platform bias to `yaw_rate_pred_rads` and recomputes residual.
- **Expected effect:** RMSE on F-150 should drop substantially (bias ≈ mean and RMSE = √(mean² + var), so removing mean keeps only var). Predicted F-150 RMSE ψ̇ ≈ √(1.06² − 0.87²) ≈ 0.60 °/s. Mach-E predicted improvement is smaller and may be partially undone by within-platform sign flip between its two segments.
- **Falsification:** RMSE Mach-E barely changes or rises (because per-segment biases cancel). RMSE F-150 stays > 1.0 °/s.

### Candidate B — Understeer-gradient (cornering compliance) yaw scaling
- **Hypothesis (physical):** Real tyres develop slip angles that reduce the actual yaw response below the kinematic-bicycle prediction. To first order, `ψ̇_actual ≈ ψ̇_kinematic / (1 + K_us · v² · δ_road)` (steady-state bicycle with understeer gradient). At low |a_y| the kinematic model is fine; at high |a_y| it over-predicts by an amount proportional to lateral acceleration.
- **Signal that suggests it:** corr(yaw_resid, |a_y|) = −0.88 on the F-150 high-speed segment; RMSE doubles from |a_y|<1 → |a_y|∈[2,3). Mach-E doesn't see enough |a_y| to confirm.
- **How to implement:** Post-process `yaw_rate_pred_rads` with a single-parameter linear correction: `ψ̇_pred_corrected = ψ̇_pred_baseline · (1 − k · |a_y_pred|)`, fit `k` per platform by minimising residual RMSE on the segments. Recompute residual columns. Implementation lives in `out/apply_understeer.py`.
- **Expected effect:** F-150 RMSE drops to ~0.6-0.7 °/s. Mach-E unchanged (|a_y| ≈ 0).
- **Falsification:** Fitted `k` is ≈ 0 or wrong sign on Mach-E.

### Candidate C — Steering actuator lag compensation (lead the delta by ~60-80 ms)
- **Hypothesis (physical):** Recorded `delta_wheel_deg` (steering wheel) precedes road-wheel reality due to mechanical compliance / EPS dynamics. Model integrates as if road wheel = steering wheel/ratio instantaneously; in fact the car responds with a small lag.
- **Signal:** cross-correlation peaks at lag −60..−80 ms.
- **How to implement:** Apply a first-order lag on `delta_road_rad` before re-running KS. Requires touching the sim generator (heavier).
- **Why not pick:** Magnitude is small; corr only lifts 0.80→0.81 on Mach-E. Time-budget-expensive vs payoff. Document as rejected.

### Candidate D — Wheelbase recalibration
- **Hypothesis:** A 5% wheelbase error scales kinematic yaw by 5%. Best-k from `pred ≈ k·meas` regression: F-150 = 1.061 (5.7% over-prediction, consistent with a longer effective wheelbase). Mach-E = 0.297 — implausibly wrong, dominated by noise (signal-to-noise too low).
- **Why not pick:** F-150 signal interacts with the understeer signal (a global `k` and an |a_y|-dependent term are entangled). Cleaner to just fit the understeer term.

## Selected for implementation (2)

- **Variant A:** constant yaw-rate bias correction (using the existing skill).
- **Variant B:** understeer-gradient correction on top of A.

Reason: A is cheapest (free skill), B targets the dominant failure mode on F-150. Stacking them tests whether the understeer term still earns its keep after bias is removed.

## Pre-committed ablation table

| Variant | Method | Expected RMSE ψ̇ Mach-E (°/s) | Expected RMSE ψ̇ F-150 (°/s) |
|---|---|---|---|
| baseline | as-is | 0.416 (actual) | 1.061 (actual) |
| +A (bias) | per-platform mean-resid added to pred | ~0.27 | ~0.60 |
| +A +B (bias + understeer) | A, then ψ̇_pred · (1 − k·\|a_y_pred\|) with `k` fit per platform | ~0.27 | ~0.40 |

## Success criterion (locked)

- **Numerical:** RMSE ψ̇ on F-150 drops ≥ 30% after A+B. Mach-E does not get worse by more than 10%.
- **Physical:** corr(resid, |a_y|) on F-150 falls below |0.3| after +B (the systematic |a_y|-coupling is gone).

## What this plan deliberately does NOT do

- No full Pacejka / non-linear tyre — overkill for 4 segments and 30 min.
- No CAN re-decoding — assume adapter outputs are correct.
- No regeneration via `code/generate_simdata_ford.py` — costly, and a post-prediction correction is sufficient for both selected variants (since we stay in speed-known lateral-only and only touch `yaw_rate_pred_rads`).
- No edits to `code/` in place. All variant logic in `out/`.
