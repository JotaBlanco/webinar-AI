# agent-09

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-09/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: pooled yaw-rate RMSE over all 520 Ford segments, masked to v>2 m/s
- **platform**: Ford segments (Mach-E + F-150 Lightning)
- **baseline_value**: 0.01474 rad/s
- **final_value**: 0.00894 rad/s
- **improvement**: −39.4% RMSE
- **top_contributor**: V4 understeer K·v²

## Honesty flags
- **declared_limitations**: `5`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "per-segment `sim.csv` files (which carry `v_mps`, `delta_road_rad`, measured `ya…" |
| contract-acknowledged | binary | True | None | "under `clamp_v_to_measured=True` — there is no lateral-prediction lever there"; "Because the speed-known clamp turns KS into a closed-form lateral predictor" |
| regime-breakdown-present | binary | False | None | _none_ |
| methodology-consistent | binary | True | None | "pooled yaw-rate RMSE over all 520 Ford segments, masked to `v > 2 m/s`"; "Shapley value over the four corrections, allocating the total MSE-drop across al…" |
| attribution-coherent | numeric | True | True | "Shapley value over the four corrections, allocating the total MSE-drop across al…" |
| honest-regression-flagged | binary | None | None | _none_ |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Agent scores against measured yaw_rate_meas_rads channel from Ford sim.csv files.
- evidence:
  > per-segment `sim.csv` files (which carry `v_mps`, `delta_road_rad`, measured `yaw_rate_meas_rads`, `a_lat_meas_mps2`, and the baseline KS prediction)

### contract-acknowledged
- result: `True`
- reasoning: Agent explicitly states velocity is clamped to measured while yaw-rate is predicted.
- evidence:
  > under `clamp_v_to_measured=True` — there is no lateral-prediction lever there
  > Because the speed-known clamp turns KS into a closed-form lateral predictor

### regime-breakdown-present
- result: `False`
- reasoning: No per-regime breakdown; only per-platform.
- evidence: _none_

### methodology-consistent
- result: `True`
- reasoning: Same pooled mask and metric used across all variants.
- evidence:
  > pooled yaw-rate RMSE over all 520 Ford segments, masked to `v > 2 m/s`
  > Shapley value over the four corrections, allocating the total MSE-drop across all 24 (n!) ordering permutations

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Shapley decomposition sums to 100% by construction.
- evidence:
  > Shapley value over the four corrections, allocating the total MSE-drop across all 24 (n!) ordering permutations

### honest-regression-flagged
- result: `None`
- reasoning: No regressions and no explicit statement.
- evidence: _none_
