# angleE-m2-agent-03

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-2/agent-03/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.01613
- **final_value**: 0.01469
- **improvement**: −8.9%
- **top_contributor**: V1 (KS recalib + per-seg gyro bias)

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `False`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "`yaw_rate_meas_rads` is measured truth (from rlog IMU, Ford-only)." |
| contract-acknowledged | binary | True | None | "Speed `v` and steering `δ` are **clamped** to measured under the speed-known ope…" |
| regime-breakdown-present | binary | True | None | "| variant | overall | straight | steady | transient |" |
| methodology-consistent | binary | True | None | "Regime split (fixed thresholds): straight 785,093 rows, steady 106,978, transien…" |
| attribution-coherent | numeric | True | True | "**Sum of marginals: −0.00050 rad/s.** Total V0→V3 delta: −0.00050. Match within …" |
| honest-regression-flagged | binary | True | None | "**V2 and V3 everywhere**: Linear ST adds front/rear slip with cornering stiffnes…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: The report names the scored channel and identifies it as measured, citing the dataset/source (rlog IMU).
- evidence:
  > `yaw_rate_meas_rads` is measured truth (from rlog IMU, Ford-only).

### contract-acknowledged
- result: `True`
- reasoning: Explicit statement of which channels are clamped to truth (v, δ) vs predicted (yaw rate).
- evidence:
  > Speed `v` and steering `δ` are **clamped** to measured under the speed-known operating contract (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). The lateral residual `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` is the only metric scored.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table includes per-regime columns (straight/steady/transient).
- evidence:
  > | variant | overall | straight | steady | transient |

### methodology-consistent
- result: `True`
- reasoning: A fixed regime split with row counts is declared once and used across every variant in the ladder table.
- evidence:
  > Regime split (fixed thresholds): straight 785,093 rows, steady 106,978, transient 21,555.

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Sum of marginal drops equals the total drop exactly, well under the 0.15 threshold.
- evidence:
  > **Sum of marginals: −0.00050 rad/s.** Total V0→V3 delta: −0.00050. Match within rounding (yes, <15%).

### honest-regression-flagged
- result: `True`
- reasoning: Regressions (V1 transient, V2, V3) are explicitly flagged with physical causes.
- evidence:
  > **V2 and V3 everywhere**: Linear ST adds front/rear slip with cornering stiffness `Cα`. With straight rows dominating sample count, an ST model that injects slip-driven yaw on essentially-straight motion (numerical slip ≠ 0 at low δ) raises straight RMSE; the prior Cα is also miscalibrated for the Mach-E platform.
