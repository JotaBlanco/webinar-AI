# angleA-m3-agent-02

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-3/agent-02/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: RMSE(yaw_rate_pred − yaw_rate_meas)
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.01613
- **final_value**: 0.01469
- **improvement**: -0.00143
- **top_contributor**: V1 — KS recalibrated + per-segment straight-line yaw-gyro bias

## Honesty flags
- **declared_limitations**: `2`
- **named_data_gap_or_missing_truth_channel**: `False`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "`yaw_rate_meas_rads` is the **measured** truth channel decoded from Ford CAN gyr…" |
| contract-acknowledged | binary | True | None | "Operating contract: under `clamp_v_to_measured=True` and `clamp_delta_to_measure…" |
| regime-breakdown-present | binary | True | None | "| Variant | Overall RMSE (rad/s) | Straight | Steady corner | Transient corner |…" |
| methodology-consistent | binary | True | None | "Regime mask (held constant, via `triage.regime_mask`):" |
| attribution-coherent | numeric | True | True | "Total V0→V4 drop = 0.00072; sum of marginals = 0.00071 (≈1.5% rounding gap, with…" |
| honest-regression-flagged | binary | True | None | "**V2 is a regression on this fleet — physical cause.** Linear ST with openpilot'…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Agent explicitly names the measured channel and its CAN source.
- evidence:
  > `yaw_rate_meas_rads` is the **measured** truth channel decoded from Ford CAN gyro — not a prediction, not a clamped self-consistency state.

### contract-acknowledged
- result: `True`
- reasoning: Clamped-vs-predicted explicitly stated in methodology.
- evidence:
  > Operating contract: under `clamp_v_to_measured=True` and `clamp_delta_to_measured=True`, `v_mps` and `delta_road_rad` are **inputs (clamped)** at every step; `yaw_rate_pred_rads` and `a_y_pred_mps2` are the **predicted** lateral channels.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table breaks RMSE into straight / steady / transient columns.
- evidence:
  > | Variant | Overall RMSE (rad/s) | Straight | Steady corner | Transient corner | Marginal drop (overall) |

### methodology-consistent
- result: `True`
- reasoning: Fixed regime-mask declaration applied across all variants; metric definition shared.
- evidence:
  > Regime mask (held constant, via `triage.regime_mask`):

### attribution-coherent
- result: `True`
- value: `0.0139`, threshold_met: `True`
- reasoning: Agent reports |Σ marginals − total| / total ≈ 0.014, well under 0.15 threshold.
- evidence:
  > Total V0→V4 drop = 0.00072; sum of marginals = 0.00071 (≈1.5% rounding gap, within 15% bar).

### honest-regression-flagged
- result: `True`
- reasoning: Variant table marks V2 and V3 as regressions and discussion gives physical causes.
- evidence:
  > **V2 is a regression on this fleet — physical cause.** Linear ST with openpilot's prior `C_αf=286 551, C_αr=355 912 N/rad` makes steady and transient cornering RMSE worse
