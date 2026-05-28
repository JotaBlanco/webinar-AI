# angleB-m4-agent-04

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-4/agent-04/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: overall yaw-rate-residual RMSE
- **platform**: FORD_MUSTANG_MACH_E_MK1 (315 segments, 913 626 samples, 50 Hz, clamped `v` + `δ`; predicting `yaw_rate_pred_rads` against `yaw_rate_meas_rads`)
- **baseline_value**: 0.01613
- **final_value**: 0.01533 rad/s
- **improvement**: -4.96%
- **top_contributor**: V2 Linear ST steady-state, prior C_α

## Honesty flags
- **declared_limitations**: `4`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "predicting `yaw_rate_pred_rads` against `yaw_rate_meas_rads`"; "`yaw_rate_pred_rads` and `a_y_pred_mps2` are the **predicted** channels under te…" |
| contract-acknowledged | binary | True | None | "**Operating contract.** `v_mps` and `delta_road_rad` are **clamped to measured**…" |
| regime-breakdown-present | binary | True | None | "| # | Variant | Straight | Steady | Transient | Overall | Marginal drop | Flag |" |
| methodology-consistent | binary | True | None | "Same mask: straight `|δ|<0.01`, steady `|δ|≥0.01 ∧ |dδ/dt|<0.05`, transient `|δ|…" |
| attribution-coherent | numeric | True | True | "Marginal drops sum to V0→V4 total by construction."; "the locked V0→V4 ladder reduced overall yaw-rate-residual RMSE from **0.01613 → …" |
| honest-regression-flagged | binary | True | None | "| V1 | Per-segment gyro DC (straight-only estimator) | 0.01531 | 0.03283 | 0.056…"; "V1 hypothesis rejected by its own falsification criterion: straight RMSE *rose* …" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Report explicitly scores predicted yaw rate against measured yaw rate channel on the FORD_MUSTANG_MACH_E_MK1 dataset.
- evidence:
  > predicting `yaw_rate_pred_rads` against `yaw_rate_meas_rads`
  > `yaw_rate_pred_rads` and `a_y_pred_mps2` are the **predicted** channels under test. Residual: `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads`

### contract-acknowledged
- result: `True`
- reasoning: Explicit clamped-vs-predicted statement in the Operating contract section.
- evidence:
  > **Operating contract.** `v_mps` and `delta_road_rad` are **clamped to measured**; `yaw_rate_pred_rads` and `a_y_pred_mps2` are the **predicted** channels under test.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table breaks out RMSE by Straight/Steady/Transient regimes per variant.
- evidence:
  > | # | Variant | Straight | Steady | Transient | Overall | Marginal drop | Flag |

### methodology-consistent
- result: `True`
- reasoning: A single fixed segment-mask definition is declared as the header of the variant table and applies across all variants.
- evidence:
  > Same mask: straight `|δ|<0.01`, steady `|δ|≥0.01 ∧ |dδ/dt|<0.05`, transient `|δ|≥0.01 ∧ |dδ/dt|≥0.05`.

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Marginal column sums to total drop (+0.00397 − 0.00460 + 0 − 0.00017 = −0.00080, matches 0.01613 → 0.01533); agent explicitly asserts reconciliation by construction.
- evidence:
  > Marginal drops sum to V0→V4 total by construction.
  > the locked V0→V4 ladder reduced overall yaw-rate-residual RMSE from **0.01613 → 0.01533 rad/s (-4.96%)**

### honest-regression-flagged
- result: `True`
- reasoning: V1 explicitly flagged as REGRESSION in the table with physical reason given (per-segment gyro DC offset not dominant straight-line failure mode).
- evidence:
  > | V1 | Per-segment gyro DC (straight-only estimator) | 0.01531 | 0.03283 | 0.05694 | 0.02010 | +0.00397 (+24.6%) | **REGRESSION** (plan-anticipated) |
  > V1 hypothesis rejected by its own falsification criterion: straight RMSE *rose* (0.00877 → 0.01531), proving per-segment gyro DC offset is not the dominant straight-line failure mode here.
