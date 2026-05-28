# Plan — variant ladder (LOCKED)

Scope: post-hoc lateral correction over the existing per-platform sim CSVs, **per-platform** fits, interleaved every-5th-sample train (k%5!=0) / test (k%5==0) split. Score on the test set only, per regime, on both Ford platforms.

Accounting scheme: **incremental** — each variant builds on the previous; the contribution attributed to a variant is `RMSE(V_{i-1}) - RMSE(V_i)` on the test set, overall. Per-regime numbers reported but not used for attribution.

## V0 — Baseline
Identity. `ψ̇_pred` as-shipped. Falsifier: must match `evals/baseline_rmse.py` exactly (overall RMSE only; baseline_rmse uses all samples, V0_test will use test split so will differ — report both).

## V1 — Per-platform static yaw-rate bias removal
Hypothesis: yaw-rate sensor / model has a constant per-platform offset visible on straights. Fit `b = median(ψ̇_pred - ψ̇_meas)` on straight samples of TRAIN. Apply `ψ̇_pred' = ψ̇_pred - b`. Per-platform.
Predicted effect: straight RMSE drops; steady/transient mostly unchanged.
Falsifier: if `|b| < 1e-4` rad/s OR straight RMSE doesn't drop, V1 fails.

## V2 — Per-platform steering-ratio / effective-L gain
Hypothesis: KS systematically over- or under-predicts steady-state yaw rate because real cars carry understeer that KS cannot. Fit scalar `g` minimising `Σ (g·ψ̇_pred_after_V1 - ψ̇_meas)²` on STEADY+TRANSIENT TRAIN samples (closed form: `g = ⟨ψ̇_pred·ψ̇_meas⟩ / ⟨ψ̇_pred²⟩`). Apply `ψ̇_pred'' = g · ψ̇_pred'`. Per-platform.
Predicted effect: steady RMSE drops; transient drops partially.
Falsifier: if `|g-1| < 0.01` OR steady RMSE doesn't drop, V2 fails.

## V3 — Coupled a_y refit
Once ψ̇ is corrected, recompute `a_y_pred = v · ψ̇_pred''` (rule 9). Not a fit; just enforces the invariant. Report a_y RMSE before/after but headline is yaw rate.

## Out-of-scope (named so it's not accidentally done)
- Per-segment bias removal (calibration, not model improvement — rule 8).
- Steering-lag fit (would need sub-sample shift; out of 15-min budget).
- Tesla scoring (no truth — rule 4).

## Schema-check gate
Every variant CSV must pass `evals/schema_check.py` (sign convention, residual columns recomputed, no NaN). If V_i fails schema, V_i is discarded and the ladder stops.
