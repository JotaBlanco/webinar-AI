# m1-agent-01

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-01/final-model/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: yaw RMSE [rad/s]
- **platform**: F-150 Lightning (51 files held out) and Mach-E (71 files held out)
- **baseline_value**: 0.01849 (F-150), 0.01506 (Mach-E)
- **final_value**: 0.01225 (F-150), 0.01018 (Mach-E)
- **improvement**: 33.7% (F-150), 32.4% (Mach-E)
- **top_contributor**: V1 (K_us understeer gradient) for F-150; V2 (alpha effective steering-ratio scale) for Mach-E

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| yaw_rate_rmse-improvement-pct | numeric | True | None | "| F-150 Lightning (51 files held out) | yaw RMSE [rad/s] | 0.01849 | 0.01225 | 3…"; "| Mach-E (71 files held out) | yaw RMSE [rad/s] | 0.01506 | 0.01018 | 32.4% |" |
| cte_rmse-improvement-pct | numeric | True | None | "| | CTE mean [m] | 74.51 | 30.03 | 60% |"; "| | CTE mean [m] | 78.40 | 62.98 | 20% |" |
| regime-breakdown-present | binary | False | None | "| platform | KPI | V0 | ours | reduction |" |
| methodology-consistent | binary | True | None | "fit per platform on 70% of the shipped Ford sim segments and evaluated on the 30…" |
| attribution-coherent | numeric | True | True | "V1 — add K_us. F-150 0.0144 -> 0.0077; Mach-E barely moves."; "V2 — add alpha (effective steering-ratio scale). Mach-E 0.0166 -> 0.0110."; "V3 — add beta (steering offset). F-150 0.0076 -> 0.0061."; "V4 (shipped) — add tau first-order lag. F-150 0.0061 -> 0.0052;
                …" |
| honest-regression-flagged | binary | False | None | "V1 — add K_us. F-150 0.0144 -> 0.0077; Mach-E barely moves." |

## Per-item reasoning
### yaw_rate_rmse-improvement-pct
- result: `True`
- value: `33.05`, threshold_met: `None`
- reasoning: Report states ~33% yaw-rate RMSE reduction vs V0 on both platforms, on a held-out split.
- evidence:
  > | F-150 Lightning (51 files held out) | yaw RMSE [rad/s] | 0.01849 | 0.01225 | 33.7% |
  > | Mach-E (71 files held out) | yaw RMSE [rad/s] | 0.01506 | 0.01018 | 32.4% |

### cte_rmse-improvement-pct
- result: `True`
- value: `40.0`, threshold_met: `None`
- reasoning: Report gives CTE mean improvements of 60% (F-150) and 20% (Mach-E); pooled approx 40%.
- evidence:
  > | | CTE mean [m] | 74.51 | 30.03 | 60% |
  > | | CTE mean [m] | 78.40 | 62.98 | 20% |

### regime-breakdown-present
- result: `False`
- reasoning: Report breaks results by platform only; no straight/cornering/transient regime split is shown anywhere.
- evidence:
  > | platform | KPI | V0 | ours | reduction |

### methodology-consistent
- result: `True`
- reasoning: Ladder uses the same yaw-RMSE metric across V0..V4 with a consistent 70/30 per-platform split declared up front; segment-set is implicitly fixed.
- evidence:
  > fit per platform on 70% of the shipped Ford sim segments and evaluated on the 30% held out

### attribution-coherent
- result: `True`
- value: `0.02`, threshold_met: `True`
- reasoning: Sequential marginal drops on F-150 (0.0067+0.0001+0.0015+0.0009=0.0092) reconcile with total V0->V4 drop of 0.0092; same on Mach-E.
- evidence:
  > V1 — add K_us. F-150 0.0144 -> 0.0077; Mach-E barely moves.
  > V2 — add alpha (effective steering-ratio scale). Mach-E 0.0166 -> 0.0110.
  > V3 — add beta (steering offset). F-150 0.0076 -> 0.0061.
  > V4 (shipped) — add tau first-order lag. F-150 0.0061 -> 0.0052;
                 Mach-E 0.0110 -> 0.0104.

### honest-regression-flagged
- result: `False`
- reasoning: Ladder is monotonic but the report contains no explicit 'no regressions observed' statement and no regression-cause column; the rubric requires one or the other.
- evidence:
  > V1 — add K_us. F-150 0.0144 -> 0.0077; Mach-E barely moves.
