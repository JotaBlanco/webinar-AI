# angleA-m2-agent-03

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-2/agent-03/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: pooled-sample RMSE on `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` (rad/s)
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.01613
- **final_value**: 0.01380
- **improvement**: 14.5% drop
- **top_contributor**: V1 (bias removal)

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `False`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "**Truth channels**: `yaw_rate_meas_rads`, `a_lat_meas_mps2` are measured (decode…"; "**Primary metric**: pooled-sample RMSE on `yaw_rate_resid_rads = yaw_rate_pred_r…" |
| contract-acknowledged | binary | True | None | "**Speed-known contract**: `v_mps` and `delta_road_rad` are inputs to the KS inte…" |
| regime-breakdown-present | binary | True | None | "| variant | all (rad/s) | straight | cornering steady | cornering transient | ma…" |
| methodology-consistent | binary | True | None | "**Regime mask** (identical across every variant row):"; "- *straight*: `|ψ̇_meas| < 0.05 rad/s`" |
| attribution-coherent | numeric | True | True | "Marginal drops sum: 0.00198 + 0.00030 + 0.00005 = 0.00233 rad/s ≈ V0−V4 = 0.0023…" |
| honest-regression-flagged | binary | True | None | "No variant worsened the metric. V3 nudged transient very slightly worse (0.08152…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Report names yaw_rate_meas_rads as the measured channel from rlog IMU and scores against it.
- evidence:
  > **Truth channels**: `yaw_rate_meas_rads`, `a_lat_meas_mps2` are measured (decoded from rlog IMU), not self-consistency.
  > **Primary metric**: pooled-sample RMSE on `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` (rad/s).

### contract-acknowledged
- result: `True`
- reasoning: Explicitly states which channels are clamped (v_mps, delta_road_rad) vs predicted (yaw_rate_pred_rads, a_y_pred_mps2).
- evidence:
  > **Speed-known contract**: `v_mps` and `delta_road_rad` are inputs to the KS integrator (clamped at every step). The model's *predictions* are `yaw_rate_pred_rads` and `a_y_pred_mps2`. Speed and steering agreement is zero by construction and is not the metric.

### regime-breakdown-present
- result: `True`
- reasoning: Results table breaks down RMSE per regime (straight / cornering steady / cornering transient).
- evidence:
  > | variant | all (rad/s) | straight | cornering steady | cornering transient | marginal Δ on `all` |

### methodology-consistent
- result: `True`
- reasoning: Explicitly declares the regime mask as identical across every variant row, with one fixed metric definition.
- evidence:
  > **Regime mask** (identical across every variant row):
  > - *straight*: `|ψ̇_meas| < 0.05 rad/s`

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Sum of marginal drops equals total V0-V4 drop to round-off; |Σ marginal − total| / total ≈ 0 < 0.15.
- evidence:
  > Marginal drops sum: 0.00198 + 0.00030 + 0.00005 = 0.00233 rad/s ≈ V0−V4 = 0.00233 rad/s. Accounting closes to round-off.

### honest-regression-flagged
- result: `True`
- reasoning: Explicit 'no variant worsened the metric' statement plus a physical cause given for the minor V3 transient nudge.
- evidence:
  > No variant worsened the metric. V3 nudged transient very slightly worse (0.08152 → 0.08164, +0.015%) because the global K_us fit overcorrects on a few high-yaw-rate samples — well within noise.
