# Plan (locked)

Platform under test: **FORD_MUSTANG_MACH_E_MK1** (primary), **FORD_F_150_LIGHTNING_MK1** (secondary, confirm transfer).
Truth channel: `yaw_rate_meas_rads`. Residual: `pred − meas`.
Train/test: every-5th-sample interleaved split, train = indices % 5 != 0, test = indices % 5 == 0.
Fit scope: **per-platform** (not per-segment). All gains/biases reported are platform-wide.

## Variant ladder

| ID | Description | Degree of freedom | Predicted effect | Falsifier |
|----|-------------|------------------|------------------|-----------|
| V0 | `yaw_rate_resid_rads` as-is | 0 | baseline | n/a |
| V1 | Subtract additive bias `b = median(pred − meas)` on **train, straight regime** | +1 (offset) | drop straight RMSE; minimal change in steady/transient | if straight RMSE does not drop ≥ 10 %, V1 failed |
| V2 | Apply multiplicative gain on `ψ̇_pred`: `ψ̇' = g · ψ̇_pred` with `g = sum(m·p)/sum(p²)` fit on **train, cornering** samples | +1 (gain) | large drop in steady & transient; small drop in straight | if steady RMSE does not drop ≥ 30 %, V2 failed |
| V3 | V2 then V1 (gain first, then residual additive bias on straight) | +2 | best overall RMSE; straight ≤ V1, steady ≤ V2 | if V3 worse than max(V1,V2) in any regime, regression |

## Coupling rule (Rule 9)
Whenever ψ̇_pred is modified, re-derive `a_y_pred = v · ψ̇'` and recompute `yaw_rate_resid_rads`, `a_y_resid_mps2` so `schema_check.py` still passes.

## Reporting
- Per-regime test-set RMSE for V0..V3.
- Δ-RMSE attribution: V1 share = (V0−V1), V2 share = (V0−V2), V3 incremental = (V2−V3).
- Same segment set across all variants.
- Flag any regression with physical cause.

Lock.
