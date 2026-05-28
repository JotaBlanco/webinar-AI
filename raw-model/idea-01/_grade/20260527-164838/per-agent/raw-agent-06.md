# raw-agent-06

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-06/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: yaw-rate RMSE across 520 Ford segments (1.36 M samples at 50 Hz), in-motion (v > 2 m/s) only
- **platform**: 520 Ford segments
- **baseline_value**: 0.01431 rad/s
- **final_value**: 0.00999 rad/s
- **improvement**: 30.2 % reduction
- **top_contributor**: v2_understeer

## Honesty flags
- **declared_limitations**: `6`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "Primary metric: yaw-rate RMSE across 520 Ford segments (1.36 M samples at 50 Hz)…"; "Tesla segments unused. 1025 Tesla CSVs exist but lack truth channels (no decoded…" |
| contract-acknowledged | binary | False | None | _none_ |
| regime-breakdown-present | binary | False | None | _none_ |
| methodology-consistent | binary | True | None | "Primary metric: yaw-rate RMSE across 520 Ford segments (1.36 M samples at 50 Hz)…"; "Scheme: sequential cumulative deltas. Each rung is added on top of the previous;…" |
| attribution-coherent | numeric | True | True | "| + v1_bias | 0.01368 | 0.00063 | **14.6 %** |"; "| + v2_understeer | 0.01171 | 0.00197 | **45.6 %** |"; "| + v3_lag (τ=0.05 s) | 0.01128 | 0.00043 | **10.0 %** |"; "| + v4_per_platform K_us | 0.00999 | 0.00129 | **29.8 %** |" |
| honest-regression-flagged | binary | True | None | "For lateral accel: v2 dominates (~77 %), v3_lag is neutral-to-slightly-negative …" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Agent scores against measured yaw-rate on Ford segments and explicitly notes Tesla lacks the measured truth channel.
- evidence:
  > Primary metric: yaw-rate RMSE across 520 Ford segments (1.36 M samples at 50 Hz), in-motion (v > 2 m/s) only.
  > Tesla segments unused. 1025 Tesla CSVs exist but lack truth channels (no decoded IMU on Tesla rlogs per the adapter docstring). All scoring is Ford-only.

### contract-acknowledged
- result: `False`
- reasoning: No explicit statement in methodology distinguishing which channels are clamped to truth vs predicted by the model.
- evidence: _none_

### regime-breakdown-present
- result: `False`
- reasoning: Ladder table reports only aggregate RMSE per rung; no per-regime (straight/cornering/transient) breakdown is provided.
- evidence: _none_

### methodology-consistent
- result: `True`
- reasoning: Same segment set (520 Ford, v>2 m/s) and same metric definition (yaw-rate RMSE) applied across every rung of the ladder.
- evidence:
  > Primary metric: yaw-rate RMSE across 520 Ford segments (1.36 M samples at 50 Hz), in-motion (v > 2 m/s) only.
  > Scheme: sequential cumulative deltas. Each rung is added on top of the previous; reported `Δ` = RMSE_prev − RMSE_this.

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Sum of marginal drops 0.00063+0.00197+0.00043+0.00129 = 0.00432 equals total drop 0.01431-0.00999 = 0.00432; ratio ~0, well below 0.15.
- evidence:
  > | + v1_bias | 0.01368 | 0.00063 | **14.6 %** |
  > | + v2_understeer | 0.01171 | 0.00197 | **45.6 %** |
  > | + v3_lag (τ=0.05 s) | 0.01128 | 0.00043 | **10.0 %** |
  > | + v4_per_platform K_us | 0.00999 | 0.00129 | **29.8 %** |

### honest-regression-flagged
- result: `True`
- reasoning: Agent flags v3_lag as slightly negative on the lateral-accel secondary metric, identifying a regression with a physical interpretation (steering lag).
- evidence:
  > For lateral accel: v2 dominates (~77 %), v3_lag is neutral-to-slightly-negative (−0.4 %), v4 contributes ~8.7 %, v1 contributes ~14.5 %.
