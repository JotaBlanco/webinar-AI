# m1-agent-05

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-05/final-model/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: Yaw-rate RMSE (rad/s)
- **platform**: FORD_F_150_LIGHTNING_MK1
- **baseline_value**: 0.01269
- **final_value**: 0.00694
- **improvement**: -45.3%
- **top_contributor**: V1 shipped: psi_dot = gain * v * (delta - delta_offset) / (L + Kus * v^2)

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| regime-breakdown-present | binary | False | None | _none_ |
| methodology-consistent | binary | None | None | _none_ |
| attribution-coherent | numeric | False | False | _none_ |
| honest-regression-flagged | binary | None | None | _none_ |

## Per-item reasoning
### regime-breakdown-present
- result: `False`
- reasoning: Headline table breaks results out by platform and KPI but never by regime (straight / cornering / transient); no per-regime table or chart is present.
- evidence: _none_

### methodology-consistent
- result: `None`
- reasoning: Report does not declare a fixed segment-set or regime-mask shared across variants; only V0 and V1 are listed with no segment-mask header.
- evidence: _none_

### attribution-coherent
- result: `False`
- value: `None`, threshold_met: `False`
- reasoning: No marginal-improvement column is provided — only a single V0→V1 step is shown, so marginal contributions cannot be reconciled against a total drop.
- evidence: _none_

### honest-regression-flagged
- result: `None`
- reasoning: Only one ladder step is shown (V0 → V1) and there is no explicit 'no regressions observed' statement, so the regression-flagging rubric is not addressed.
- evidence: _none_
