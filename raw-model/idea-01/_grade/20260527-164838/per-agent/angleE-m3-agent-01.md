# angleE-m3-agent-01

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-3/agent-01/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: RMSE overall (rad/s)
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.01612
- **final_value**: 0.01664
- **improvement**: −0.00051 = total drop V0→V3
- **top_contributor**: V1

## Honesty flags
- **declared_limitations**: `2`
- **named_data_gap_or_missing_truth_channel**: `False`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "Truth channel: `yaw_rate_meas_rads` (Ford `sim.csv`)" |
| contract-acknowledged | binary | True | None | "Operating contract: KS runs with `clamp_v_to_measured=True` and `clamp_delta_to_…" |
| regime-breakdown-present | binary | True | None | "| Variant | Description | RMSE overall (rad/s) | RMSE straight | RMSE steady | R…" |
| methodology-consistent | binary | True | None | "Same regime column reused from the parent skill to avoid the documented mask-mis…" |
| attribution-coherent | numeric | True | True | "Sum of marginals: −0.00051 = total drop V0→V3 (gap 0.00%, well inside the 15% to…" |
| honest-regression-flagged | binary | True | None | "**V2 vs V1, all three regimes.** Linear-ST steady-state gain `v·δ / (L·(1 + K_us…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: The report names the measured channel and cites the dataset source.
- evidence:
  > Truth channel: `yaw_rate_meas_rads` (Ford `sim.csv`)

### contract-acknowledged
- result: `True`
- reasoning: Explicitly states clamped channels (v, delta) and predicted channel (yaw rate).
- evidence:
  > Operating contract: KS runs with `clamp_v_to_measured=True` and `clamp_delta_to_measured=True`. Speed and steering are inputs; the lateral residual `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` is the only metric.

### regime-breakdown-present
- result: `True`
- reasoning: Per-regime RMSE columns (straight/steady/transient) are presented for every variant.
- evidence:
  > | Variant | Description | RMSE overall (rad/s) | RMSE straight | RMSE steady | RMSE transient | Marginal Δ overall |

### methodology-consistent
- result: `True`
- reasoning: Explicit declaration that the same regime mask/metric is used across variants.
- evidence:
  > Same regime column reused from the parent skill to avoid the documented mask-mismatch trap.

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Sum of marginals reconciles to total drop with ~0% gap, well under the 0.15 threshold.
- evidence:
  > Sum of marginals: −0.00051 = total drop V0→V3 (gap 0.00%, well inside the 15% tolerance).

### honest-regression-flagged
- result: `True`
- reasoning: Regressions for V2 and V3 are explicitly flagged with physical-cause explanations.
- evidence:
  > **V2 vs V1, all three regimes.** Linear-ST steady-state gain `v·δ / (L·(1 + K_us·v²))` under-predicts yaw rate where transients and tyre nonlinearity dominate.
