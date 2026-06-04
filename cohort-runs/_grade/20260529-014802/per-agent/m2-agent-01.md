# m2-agent-01

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-01/final-model/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: Yaw-rate RMSE (rad/s)
- **platform**: Lightning (single segment spot-check)
- **baseline_value**: not measured
- **final_value**: not measured
- **improvement**: not measured
- **top_contributor**: linear-bicycle steady-state yaw rate with understeer gradient K_us

## Honesty flags
- **declared_limitations**: `5`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| regime-breakdown-present | binary | False | None | "Could not run quantitative evaluation: `python3` execution was blocked in the ag…" |
| methodology-consistent | binary | False | None | "| KPI | V0 (kinematic single-track) | Final (linear-bicycle SS, α=0.7) |" |
| attribution-coherent | numeric | False | False | "Therefore no measured V0 vs final-model numbers are reported here." |
| honest-regression-flagged | binary | None | None | _none_ |

## Per-item reasoning
### regime-breakdown-present
- result: `False`
- reasoning: No per-regime (straight/cornering/transient) breakdown table or chart is present; only one hand-inspected segment is shown.
- evidence:
  > Could not run quantitative evaluation: `python3` execution was blocked in the agent sandbox.

### methodology-consistent
- result: `False`
- reasoning: The variant table has only V0 and final with 'not measured' entries; no fixed segment-set or regime-mask declaration shared across variants.
- evidence:
  > | KPI | V0 (kinematic single-track) | Final (linear-bicycle SS, α=0.7) |

### attribution-coherent
- result: `False`
- value: `None`, threshold_met: `False`
- reasoning: No marginal-improvement column nor total-drop value present; attribution coherence cannot be computed.
- evidence:
  > Therefore no measured V0 vs final-model numbers are reported here.

### honest-regression-flagged
- result: `None`
- reasoning: not addressed in report — no variant ladder with regressions and no explicit 'no regressions observed' statement.
- evidence: _none_
