# m2-agent-04

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-04/final-model/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: Yaw-rate RMSE (rad/s)
- **platform**: FORD_F_150_LIGHTNING_MK1, FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.01433
- **final_value**: 0.00711
- **improvement**: -50%
- **top_contributor**: linear bicycle steady-state expression (K_us * v^2 understeer term)

## Honesty flags
- **declared_limitations**: `4`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| yaw_rate_rmse-improvement-pct | numeric | True | None | "| Yaw-rate RMSE (rad/s)   | 0.01433  | 0.00711  | -50%     |" |
| cte_rmse-improvement-pct | numeric | True | None | "| Distance-CTE RMSE (m)   | 144.18   | 92.86    | -36%     |" |
| regime-breakdown-present | binary | True | None | "Per-regime yaw-rate RMSE (full data, v > 2 m/s):"; "| straight  | 0.00945  | 0.00670  |"; "| steady    | 0.02812  | 0.01252  |"; "| transient | 0.03825  | 0.02041  |" |
| methodology-consistent | binary | True | None | "Results on held-out dev (30%, 125 segs)"; "Per-regime yaw-rate RMSE (full data, v > 2 m/s):" |
| attribution-coherent | numeric | None | None | _none_ |
| honest-regression-flagged | binary | True | None | "## What didn't help (and was tried)"; "**τ > 0.10 s** hurts steady-state RMSE more than it helps transients."; "**Trying to fit Tesla**: no `yaw_rate_meas_rads` truth channel in the sim CSVs —…" |

## Per-item reasoning
### yaw_rate_rmse-improvement-pct
- result: `True`
- value: `50.0`, threshold_met: `None`
- reasoning: Report states a 50% reduction in yaw-rate RMSE on held-out dev (0.01433 -> 0.00711).
- evidence:
  > | Yaw-rate RMSE (rad/s)   | 0.01433  | 0.00711  | -50%     |

### cte_rmse-improvement-pct
- result: `True`
- value: `36.0`, threshold_met: `None`
- reasoning: Report states a 36% reduction in Distance-CTE RMSE on held-out dev (144.18 -> 92.86).
- evidence:
  > | Distance-CTE RMSE (m)   | 144.18   | 92.86    | -36%     |

### regime-breakdown-present
- result: `True`
- reasoning: Report includes an explicit per-regime breakdown (straight / steady / transient) for yaw-rate RMSE.
- evidence:
  > Per-regime yaw-rate RMSE (full data, v > 2 m/s):
  > | straight  | 0.00945  | 0.00670  |
  > | steady    | 0.02812  | 0.01252  |
  > | transient | 0.03825  | 0.02041  |

### methodology-consistent
- result: `True`
- reasoning: Tables share consistent captioning with explicit segment-set / regime-mask declarations (dev split definition; regime mask v > 2 m/s).
- evidence:
  > Results on held-out dev (30%, 125 segs)
  > Per-regime yaw-rate RMSE (full data, v > 2 m/s):

### attribution-coherent
- result: `None`
- value: `None`, threshold_met: `None`
- reasoning: No marginal-improvement column per variant; the report presents a single V0 -> V_final comparison without a ladder of variants summing to the total drop.
- evidence: _none_

### honest-regression-flagged
- result: `True`
- reasoning: Report includes a 'What didn't help' section explicitly enumerating variants that worsened metrics with physical reasons.
- evidence:
  > ## What didn't help (and was tried)
  > **τ > 0.10 s** hurts steady-state RMSE more than it helps transients.
  > **Trying to fit Tesla**: no `yaw_rate_meas_rads` truth channel in the sim CSVs — Tesla path is V0 passthrough.
