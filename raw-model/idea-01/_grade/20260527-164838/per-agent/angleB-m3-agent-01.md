# angleB-m3-agent-01

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-3/agent-01/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: RMSE of `pred − meas` over 315 segments / 913 626 samples at 50 Hz
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.01613
- **final_value**: 0.01530
- **improvement**: V0→V4 drop = 0.0008 rad/s (~5%)
- **top_contributor**: V1 KS + per-seg straight-line bias

## Honesty flags
- **declared_limitations**: `5`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "Predicted channel = `yaw_rate_pred_rads`. Truth = `yaw_rate_meas_rads`."; "Platform: `FORD_MUSTANG_MACH_E_MK1` (Tesla excluded — no IMU truth; F-150 not us…" |
| contract-acknowledged | binary | True | None | "Operating contract:** `v` and `δ` clamped to measured each step. Predicted chann…" |
| regime-breakdown-present | binary | True | None | "| Variant | all | straight | steady | transient | marginal drop |" |
| methodology-consistent | binary | True | None | "Metric = RMSE of `pred − meas` over 315 segments / 913 626 samples at 50 Hz."; "Different segment set across rungs — same 315-segment Mach-E set used for every …" |
| attribution-coherent | numeric | True | True | "Accounting scheme:** sequential marginal drop on `all` regime RMSE; marginal sum…" |
| honest-regression-flagged | binary | True | None | "| V2 ST steady-state, prior C_α | 0.01551 | 0.00339 | 0.03430 | 0.06277 | +0.000…"; "**V2 regression (+0.00082):** Linear-ST steady-state gain with openpilot's prior…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Scored against measured yaw_rate_meas_rads on the Mach-E platform, with Tesla explicitly excluded for lacking IMU truth.
- evidence:
  > Predicted channel = `yaw_rate_pred_rads`. Truth = `yaw_rate_meas_rads`.
  > Platform: `FORD_MUSTANG_MACH_E_MK1` (Tesla excluded — no IMU truth; F-150 not used to keep one platform per ladder).

### contract-acknowledged
- result: `True`
- reasoning: Methodology header explicitly names clamped (v, δ) vs predicted (yaw_rate_pred_rads) channels.
- evidence:
  > Operating contract:** `v` and `δ` clamped to measured each step. Predicted channel = `yaw_rate_pred_rads`. Truth = `yaw_rate_meas_rads`.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table breaks RMSE out into straight / steady / transient regimes alongside the aggregate.
- evidence:
  > | Variant | all | straight | steady | transient | marginal drop |

### methodology-consistent
- result: `True`
- reasoning: Fixed 315-segment Mach-E set and identical RMSE metric declared, and explicitly re-affirmed as held constant across rungs.
- evidence:
  > Metric = RMSE of `pred − meas` over 315 segments / 913 626 samples at 50 Hz.
  > Different segment set across rungs — same 315-segment Mach-E set used for every variant.

### attribution-coherent
- result: `True`
- value: `0.012`, threshold_met: `True`
- reasoning: Agent reports |Σ marginal − total| / total = 1.2%, well under the 15% threshold; marginal column and V0→V4 total both present.
- evidence:
  > Accounting scheme:** sequential marginal drop on `all` regime RMSE; marginal sum vs total V0→V4 gap = -1.2% (well inside 15%).

### honest-regression-flagged
- result: `True`
- reasoning: V2 row flagged as regression in the table and given a physical cause (under-rotation from too-stiff prior C_α).
- evidence:
  > | V2 ST steady-state, prior C_α | 0.01551 | 0.00339 | 0.03430 | 0.06277 | +0.00082 (regression) |
  > **V2 regression (+0.00082):** Linear-ST steady-state gain with openpilot's prior C_α *under-rotates* the car vs KS on steady and transient regimes. Priors 287/356 kN/rad — likely too stiff for these tyres/roads.
