# agent-04

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-04/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: Yaw-rate RMS residual
- **platform**: all 545 Ford segments (Mach-E + F-150 Lightning)
- **baseline_value**: 0.01804 rad/s (1.034 °/s)
- **final_value**: 0.01191 rad/s (0.682 °/s)
- **improvement**: 34% reduction
- **top_contributor**: V1 hygiene

## Honesty flags
- **declared_limitations**: `6`
- **named_data_gap_or_missing_truth_channel**: `False`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "**Yaw-rate RMS residual** across all 545 Ford segments (Mach-E + F-150 Lightning…" |
| contract-acknowledged | binary | True | None | "The KS prediction is `ψ̇ = (v / L) · tan(δ)` with measured `v` and `δ` clamped a…" |
| regime-breakdown-present | binary | False | None | "Per-platform on V4: Mach-E 0.700 °/s, F-150 0.656 °/s" |
| methodology-consistent | binary | True | None | "**Yaw-rate RMS residual** across all 545 Ford segments"; "All parameters were fit on the first half of each segment in time; metrics repor…" |
| attribution-coherent | numeric | True | True | "| V1 hygiene | 0.01804 | 0.01488 | 0.00316 | **51.5%** |"; "| V4 understeer + refit bias | 0.01437 | 0.01191 | 0.00246 | **40.1%** |" |
| honest-regression-flagged | binary | None | None | _none_ |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Report scores against measured yaw-rate on Ford segments.
- evidence:
  > **Yaw-rate RMS residual** across all 545 Ford segments (Mach-E + F-150 Lightning), evaluated on held-out test split (50% of each segment)

### contract-acknowledged
- result: `True`
- reasoning: Methodology explicitly states v and δ are clamped (measured) and ψ̇ is predicted.
- evidence:
  > The KS prediction is `ψ̇ = (v / L) · tan(δ)` with measured `v` and `δ` clamped at every step (speed-known lateral-only mode).

### regime-breakdown-present
- result: `False`
- reasoning: Per-platform breakdown given but no straight/cornering/transient regime segmentation.
- evidence:
  > Per-platform on V4: Mach-E 0.700 °/s, F-150 0.656 °/s

### methodology-consistent
- result: `True`
- reasoning: Same metric and segment set applied uniformly across the ladder.
- evidence:
  > **Yaw-rate RMS residual** across all 545 Ford segments
  > All parameters were fit on the first half of each segment in time; metrics reported on the second half.

### attribution-coherent
- result: `True`
- value: `0.0007`, threshold_met: `True`
- reasoning: Sum of marginal drops matches total drop within rounding error.
- evidence:
  > | V1 hygiene | 0.01804 | 0.01488 | 0.00316 | **51.5%** |
  > | V4 understeer + refit bias | 0.01437 | 0.01191 | 0.00246 | **40.1%** |

### honest-regression-flagged
- result: `None`
- reasoning: No regression occurred and no explicit 'no regressions observed' statement.
- evidence: _none_
