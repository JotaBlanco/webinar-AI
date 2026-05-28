# Plan — locked variant ladder

Platform of record: **FORD_MUSTANG_MACH_E_MK1** (larger sample, openpilot first-class port).
Sanity-replicate top variants on **FORD_F_150_LIGHTNING_MK1**.

Train/test: interleaved every-5th-sample split (test = idx % 5 == 0). All RMSEs reported on **test** mask. Same regime breakout as `evals/baseline_rmse.py`.

Accounting scheme: **cumulative**. Each variant V_k extends V_{k-1}; "contribution" = RMSE(V_{k-1}) − RMSE(V_k) on test, overall and by regime.

## Variants

- **V0 — baseline**. No preprocessing. `yaw_rate_resid_rads` as shipped.
  - Hypothesis: this is what the team currently reports.
  - Falsifier: must match `evals/baseline_rmse.py` numbers exactly.

- **V1 — per-platform static yaw bias**. Subtract `median(pred − meas)` taken on TRAIN straight-line samples only.
  - DoF added: 1 scalar / platform.
  - Predicted effect: drops straight RMSE strongly; modest gains on steady; negligible on transient.
  - Falsifier: if straight-RMSE doesn't drop ≥ 30%, the bias isn't static.

- **V2 — per-platform yaw-rate gain (kinematic-prediction slope)**. Fit `meas ≈ a + b·pred` on TRAIN cornering samples (|δ_road|≥0.01). Use `pred_corrected = (pred − a) / b`.
  - DoF: 2 (intercept + slope) — note intercept subsumes V1 bias, so we compose by first applying V1 then fitting `b` on residuals; report b−1.
  - Predicted effect: drops steady-state RMSE.
  - Falsifier: if `b` is within 0.98–1.02 of 1, the gain explanation is rejected.

- **V3 — understeer-gradient correction**. Fit `pred_corrected = pred / (1 + K · v² · pred)` (linearised Ackermann-with-understeer), K per-platform on TRAIN cornering samples.
  - DoF: 1.
  - Predicted effect: drops transient & high-a_y RMSE.
  - Falsifier: if K ≤ 0 (counter-physical) or transient RMSE worsens, the gradient hypothesis is rejected.

## Schema check
Every variant CSV (for one segment) is re-emitted with `yaw_rate_pred_rads` updated; `a_y_pred_mps2 = v_mps · yaw_rate_pred_rads` (rule 9); residuals recomputed `pred − meas`. `evals/schema_check.py` must pass.

## Honesty contract
If the data invalidates a variant, ship the partial result and document the regression in the report. Do not re-tune.
