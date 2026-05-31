# m2-agent-03

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-03/final-model/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: yaw-rate RMSE
- **platform**: Ford segments
- **baseline_value**: V0 over-predicts yaw rate by ~30-40 %
- **final_value**: L / (L+K_us*v^2) = 0.74
- **improvement**: ~30-40 % over-prediction reclaimed
- **top_contributor**: V1 linear-bicycle steady-state

## Honesty flags
- **declared_limitations**: `4`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| regime-breakdown-present | binary | False | None | "Every KPI claim in this report is a derivation, not a measurement." |
| methodology-consistent | binary | False | None | "Every KPI claim in this report is a derivation, not a measurement." |
| attribution-coherent | numeric | False | False | "Every KPI claim in this report is a derivation, not a measurement." |
| honest-regression-flagged | binary | False | None | "in transients it is no worse, and arguably better because the magnitude is right…" |

## Per-item reasoning
### regime-breakdown-present
- result: `False`
- reasoning: No per-regime table or chart of either KPI; only a qualitative remark about high-speed steady-cornering regimes.
- evidence:
  > Every KPI claim in this report is a derivation, not a measurement.

### methodology-consistent
- result: `False`
- reasoning: No variant table with a fixed segment-set / regime-mask declaration; only a single V1 model is described, no ladder.
- evidence:
  > Every KPI claim in this report is a derivation, not a measurement.

### attribution-coherent
- result: `False`
- value: `None`, threshold_met: `False`
- reasoning: No marginal-improvement column and no total-drop value are reported; attribution cannot be reconciled.
- evidence:
  > Every KPI claim in this report is a derivation, not a measurement.

### honest-regression-flagged
- result: `False`
- reasoning: No variant table with regression rows and no explicit 'no regressions observed' statement; only a hand-wave about transients.
- evidence:
  > in transients it is no worse, and arguably better because the magnitude is right even if the phase is uncorrected.
