# agent-04

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-04/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: Yaw-rate RMS residual
- **platform**: all 545 Ford segments (Mach-E + F-150 Lightning)
- **baseline_value**: 0.01804 rad/s / 1.034 °/s
- **final_value**: 0.01191 rad/s / 0.682 °/s
- **improvement**: 34% reduction in RMS yaw-rate residual
- **top_contributor**: V1 hygiene

## Honesty flags
- **declared_limitations**: `6`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "**Yaw-rate RMS residual** across all 545 Ford segments (Mach-E + F-150 Lightning…"; "The KS prediction is `ψ̇ = (v / L) · tan(δ)` with measured `v` and `δ` clamped a…" |
| contract-acknowledged | binary | True | None | "The KS prediction is `ψ̇ = (v / L) · tan(δ)` with measured `v` and `δ` clamped a…" |
| regime-breakdown-present | binary | False | None | "Per-platform on V4: Mach-E 0.700 °/s, F-150 0.656 °/s — the truck is actually a …" |
| methodology-consistent | binary | True | None | "**Yaw-rate RMS residual** across all 545 Ford segments (Mach-E + F-150 Lightning…"; "All parameters were fit on the first half of each segment in time; metrics repor…" |
| attribution-coherent | numeric | True | True | "| V1 hygiene | 0.01804 | 0.01488 | 0.00316 | **51.5%** |"; "| V2 steering-bias | 0.01488 | 0.01477 | 0.00012 | 1.9% |"; "| V3 transport-lag (τ = 60 ms) | 0.01477 | 0.01437 | 0.00040 | 6.5% |"; "| V4 understeer + refit bias | 0.01437 | 0.01191 | 0.00246 | **40.1%** |" |
| honest-regression-flagged | binary | None | None | _none_ |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Report scores against measured yaw-rate (ψ̇_meas) on Ford segments, with v and δ clamped — yaw-rate is the predicted/measured comparison, identified as measured from the dataset.
- evidence:
  > **Yaw-rate RMS residual** across all 545 Ford segments (Mach-E + F-150 Lightning), evaluated on held-out test split (50% of each segment)
  > The KS prediction is `ψ̇ = (v / L) · tan(δ)` with measured `v` and `δ` clamped at every step (speed-known lateral-only mode).

### contract-acknowledged
- result: `True`
- reasoning: Explicit statement that v and δ are clamped (measured) and ψ̇ is predicted by the model — clamped-vs-predicted contract is named in methodology.
- evidence:
  > The KS prediction is `ψ̇ = (v / L) · tan(δ)` with measured `v` and `δ` clamped at every step (speed-known lateral-only mode). I left the integrator alone and improved the prediction formula

### regime-breakdown-present
- result: `False`
- reasoning: Only per-platform breakdown is given; no straight/cornering/transient regime segmentation table or chart is present.
- evidence:
  > Per-platform on V4: Mach-E 0.700 °/s, F-150 0.656 °/s — the truck is actually a touch easier to predict (longer wheelbase, less aggressive driving in the segments).

### methodology-consistent
- result: `True`
- reasoning: Same metric (yaw-rate RMS residual) and same segment set (545 Ford segments, second-half test split) is declared once and applied to every ladder variant in the table.
- evidence:
  > **Yaw-rate RMS residual** across all 545 Ford segments (Mach-E + F-150 Lightning), evaluated on held-out test split (50% of each segment)
  > All parameters were fit on the first half of each segment in time; metrics reported on the second half.

### attribution-coherent
- result: `True`
- value: `0.0040650406504`, threshold_met: `True`
- reasoning: Sum of marginal drops 0.00316+0.00012+0.00040+0.00246 = 0.00614; total drop 0.01804-0.01191 = 0.00613; |0.00614-0.00613|/0.00613 ≈ 0.0016, well below 0.15.
- evidence:
  > | V1 hygiene | 0.01804 | 0.01488 | 0.00316 | **51.5%** |
  > | V2 steering-bias | 0.01488 | 0.01477 | 0.00012 | 1.9% |
  > | V3 transport-lag (τ = 60 ms) | 0.01477 | 0.01437 | 0.00040 | 6.5% |
  > | V4 understeer + refit bias | 0.01437 | 0.01191 | 0.00246 | **40.1%** |

### honest-regression-flagged
- result: `None`
- reasoning: No regressions occurred in the ladder, and the report does not include an explicit 'no regressions observed' statement.
- evidence: _none_
