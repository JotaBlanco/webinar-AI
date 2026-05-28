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
| truth-channel-correct | binary | True | None | "**Truth channels**: `yaw_rate_meas_rads`, `a_lat_meas_mps2` are measured (decode…" |
| contract-acknowledged | binary | True | None | "**Speed-known contract**: `v_mps` and `delta_road_rad` are inputs to the KS inte…" |
| regime-breakdown-present | binary | True | None | "| variant | all (rad/s) | straight | cornering steady | cornering transient | ma…" |
| methodology-consistent | binary | True | None | "**Regime mask** (identical across every variant row):" |
| attribution-coherent | numeric | True | True | "Marginal drops sum: 0.00198 + 0.00030 + 0.00005 = 0.00233 rad/s ≈ V0−V4 = 0.0023…" |
| honest-regression-flagged | binary | True | None | "No variant worsened the metric. V3 nudged transient very slightly worse (0.08152…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Explicitly names yaw_rate_meas_rads as the measured truth channel, citing rlog IMU as source.
- evidence:
  > **Truth channels**: `yaw_rate_meas_rads`, `a_lat_meas_mps2` are measured (decoded from rlog IMU), not self-consistency.

### contract-acknowledged
- result: `True`
- reasoning: Explicit clamped-vs-predicted statement identifying which channels are inputs vs predictions.
- evidence:
  > **Speed-known contract**: `v_mps` and `delta_road_rad` are inputs to the KS integrator (clamped at every step). The model's *predictions* are `yaw_rate_pred_rads` and `a_y_pred_mps2`.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table breaks out RMSE per regime (straight / cornering steady / cornering transient).
- evidence:
  > | variant | all (rad/s) | straight | cornering steady | cornering transient | marginal Δ on `all` |

### methodology-consistent
- result: `True`
- reasoning: Explicitly declares that the same regime mask is used identically across every variant row.
- evidence:
  > **Regime mask** (identical across every variant row):

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Marginal sum equals total drop exactly; |Σ - total|/total ≈ 0, well below 0.15.
- evidence:
  > Marginal drops sum: 0.00198 + 0.00030 + 0.00005 = 0.00233 rad/s ≈ V0−V4 = 0.00233 rad/s. Accounting closes to round-off.

### honest-regression-flagged
- result: `True`
- reasoning: Explicit 'no variant worsened' statement plus a physical-cause note for the tiny V3 transient nudge.
- evidence:
  > No variant worsened the metric. V3 nudged transient very slightly worse (0.08152 → 0.08164, +0.015%) because the global K_us fit overcorrects on a few high-yaw-rate samples — well within noise.
