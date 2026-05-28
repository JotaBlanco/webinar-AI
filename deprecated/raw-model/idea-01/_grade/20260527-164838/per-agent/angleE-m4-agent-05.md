# angleE-m4-agent-05

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-4/agent-05/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: RMSE(yaw_rate_resid_rads)
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.01613
- **final_value**: 0.01663
- **improvement**: −0.00051 rad/s
- **top_contributor**: V1

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `False`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "`yaw_rate_meas_rads` is the measured truth channel." |
| contract-acknowledged | binary | True | None | "`v_mps` and `delta_road_rad` are **clamped to measured**; speed-state agreement …" |
| regime-breakdown-present | binary | True | None | "| variant | description | overall RMSE | straight | steady | transient | margina…" |
| methodology-consistent | binary | True | None | "Metric: `RMSE(yaw_rate_resid_rads)` overall and per regime (straight / steady / …" |
| attribution-coherent | numeric | True | True | "Sum of marginals = `+0.00143 − 0.00184 − 0.00011 = −0.00051 rad/s`, exactly equa…" |
| honest-regression-flagged | binary | True | None | "**V2 vs V1, transient regime:** +0.00555 rad/s. Physical cause expected: Linear …" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Report explicitly names the measured yaw_rate channel as the scored truth channel.
- evidence:
  > `yaw_rate_meas_rads` is the measured truth channel.

### contract-acknowledged
- result: `True`
- reasoning: Methodology explicitly states which channels are clamped vs measured.
- evidence:
  > `v_mps` and `delta_road_rad` are **clamped to measured**; speed-state agreement is zero by construction and is **not** the metric.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table includes per-regime (straight/steady/transient) RMSE columns.
- evidence:
  > | variant | description | overall RMSE | straight | steady | transient | marginal Δ overall |

### methodology-consistent
- result: `True`
- reasoning: Single fixed metric and regime-mask declared up front and used across all variants in the ladder.
- evidence:
  > Metric: `RMSE(yaw_rate_resid_rads)` overall and per regime (straight / steady / transient) using the skill's `triage.regime_mask`.

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Marginal sum reconciles exactly with total drop, ratio 1.000 (well under 0.15 tolerance).
- evidence:
  > Sum of marginals = `+0.00143 − 0.00184 − 0.00011 = −0.00051 rad/s`, exactly equal to `RMSE(V0) − RMSE(V3)` (ratio 1.000, within the 15% tolerance).

### honest-regression-flagged
- result: `True`
- reasoning: Regression Flags section explicitly enumerates regressions with physical causes.
- evidence:
  > **V2 vs V1, transient regime:** +0.00555 rad/s. Physical cause expected: Linear ST is a *steady-state* model; transients excite yaw-rate dynamics (`I_z ψ̈`) that the model can't represent.
