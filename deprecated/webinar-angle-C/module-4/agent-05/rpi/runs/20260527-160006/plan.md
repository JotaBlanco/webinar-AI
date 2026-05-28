# Plan — locked variant ladder

Platform: **FORD_MUSTANG_MACH_E_MK1** (primary). F-150 Lightning replicated as a generalisation check.

Regime mask: from `baseline-residual` (locked across the ladder).
Train/test: interleaved — every 5th sample → test; fits use train, RMSE reported on test (per `ablation-study`).
Same segment set across all variants. Additive, monotone, fixed order.

## Ladder

### V0 — as-is residual (no preprocessing)
- Hypothesis: this is what KS produces; ceiling for what "doing nothing" delivers.
- DOF added: 0.
- Predicted direction: baseline.
- Success criterion: matches `evals/baseline_rmse.py` numerically.

### V1 — per-platform constant bias (1 DOF)
- Hypothesis: there is a constant zero-offset between sim ψ̇ and measured ψ̇ — sensor mounting, integrator init, etc.
- DOF added: 1 (scalar bias `b` such that `ψ̇_pred' = ψ̇_pred − b`).
- Fit: `b = mean(ψ̇_pred − ψ̇_meas)` on train.
- Predicted direction: small drop on straight (where bias dominates), negligible elsewhere.
- Falsifiable: if straight-regime RMSE doesn't drop, there is no constant offset and this variant did nothing.
- Per-platform fit (one scalar per platform).

### V2 — per-platform steering-gain scale (1 DOF)
- Hypothesis: the kinematic gain `v·tan(δ)/L` is mis-scaled — openpilot's steer ratio or wheelbase is slightly off vs the actual vehicle (Ackermann compliance, tyre scrub).
- DOF added: 1 (scalar `k` such that `ψ̇_pred' = k · (ψ̇_pred − b)`).
- Fit: linear regression `k = ⟨(ψ̇_pred−b)·ψ̇_meas⟩ / ⟨(ψ̇_pred−b)²⟩` on cornering samples in train.
- Predicted direction: largest drop on steady cornering.
- Falsifiable: if steady-cornering RMSE doesn't drop, KS gain is already correct.
- Per-platform.

### V3 — per-platform time lag (1 DOF, integer samples)
- Hypothesis: real ψ̇ lags δ through tyre relaxation length / CAN-bus delay. KS responds instantly.
- DOF added: 1 (integer lag `n` ∈ [0, 10] samples, i.e. ≤ 200 ms at 50 Hz).
- Fit: scan `n` on train, pick the `n` that minimises train RMSE of `ψ̇_pred(t−n·dt)·k − b vs ψ̇_meas(t)`.
- Predicted direction: largest drop on transient cornering.
- Falsifiable: if transient RMSE doesn't drop, the lag isn't a dominant transient term.
- Per-platform.

### V4 — per-segment additive bias (calibration, not modelling)
- Hypothesis: each segment has its own residual mean (IMU mounting / temperature drift). Per-segment bias captures it.
- DOF added: ~1 per segment.
- Fit: subtract train mean of residual within each segment.
- **Label: per-segment (calibration).** This is NOT model improvement — it memorises a sensor offset. Reported separately so a stakeholder doesn't confuse it with model fidelity.
- Falsifiable: if it doesn't improve straight-regime RMSE on test, even the calibration story is wrong.

## Attribution-coherence target

`|Σ marginals − total drop| / |total drop| < 0.15`.

## Locked

This plan is locked. If V2 or V3 regress, they are flagged with physical cause and kept in the table.
