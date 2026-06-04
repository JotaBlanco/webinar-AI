# m2-agent-02

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-02/final-model/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: yaw-rate RMSE
- **platform**: TESLA_MODEL_3, FORD_MUSTANG_MACH_E_MK1, FORD_F_150_LIGHTNING_MK1
- **baseline_value**: NOT MEASURED
- **final_value**: NOT MEASURED
- **improvement**: roughly a 22-27% reduction in absolute yaw-rate prediction at highway speeds
- **top_contributor**: linear-bicycle steady-state + first-order yaw lag

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| regime-breakdown-present | binary | False | None | "**Self-evaluation numbers:** NOT MEASURED." |
| methodology-consistent | binary | False | None | "**Self-evaluation numbers:** NOT MEASURED. The harness denied every attempt to r…" |
| attribution-coherent | numeric | False | False | "**Self-evaluation numbers:** NOT MEASURED." |
| honest-regression-flagged | binary | False | None | "**No empirical validation.** Without python, every "test" is just code review." |

## Per-item reasoning
### regime-breakdown-present
- result: `False`
- reasoning: No per-regime (straight / cornering / transient) breakdown of either KPI is present; the report has no regime table or chart, only an analytical expectation.
- evidence:
  > **Self-evaluation numbers:** NOT MEASURED.

### methodology-consistent
- result: `False`
- reasoning: There is no variant table with a shared segment-set / regime-mask declaration; only V0 vs V1 narrative without consistent segment definitions.
- evidence:
  > **Self-evaluation numbers:** NOT MEASURED. The harness denied every attempt to run `python3` (both for direct smoke-tests and for the score-model skill), so I cannot quote concrete RMSE deltas.

### attribution-coherent
- result: `False`
- value: `None`, threshold_met: `False`
- reasoning: No marginal-improvement column and no total-drop value; nothing to reconcile because no measurements were produced.
- evidence:
  > **Self-evaluation numbers:** NOT MEASURED.

### honest-regression-flagged
- result: `False`
- reasoning: No variant table with regression rows and no explicit 'no regressions observed' statement; the agent admits no empirical comparison was performed.
- evidence:
  > **No empirical validation.** Without python, every "test" is just code review.
