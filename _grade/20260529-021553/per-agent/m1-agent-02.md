# m1-agent-02

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-02/final-model/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: Yaw RMSE
- **platform**: FORD_F_150_LIGHTNING_MK1 (n=70)
- **baseline_value**: 0.01225 rad/s
- **final_value**: 0.00547 rad/s
- **improvement**: -55%
- **top_contributor**: _not stated_

## Honesty flags
- **declared_limitations**: `1`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| regime-breakdown-present | binary | False | None | "| FORD_F_150_LIGHTNING_MK1 (n=70) | 0.01225 rad/s | 0.00547 rad/s (-55%) | 71.8 …" |
| methodology-consistent | binary | False | None | "Coefficients fit on a random 60% of segments per platform with scipy.optimize.le…" |
| attribution-coherent | numeric | False | False | "- V0 - pure KS (baseline in yaw_rate_pred_rads): yr = v*tan(delta)/L."; "- V1 - linear-tire understeer: yr_ss = v*delta / (L + K_us*v^2)."; "- V2 - steering scale + offset: delta_eff = s*delta_road - delta_0."; "- V3 - 1st-order yaw lag (tau ~ 50 ms) on yr_ss." |
| honest-regression-flagged | binary | None | None | _none_ |

## Per-item reasoning
### regime-breakdown-present
- result: `False`
- reasoning: Headline table only breaks down by platform, not by regime (straight/cornering/transient); no per-regime table or chart is present.
- evidence:
  > | FORD_F_150_LIGHTNING_MK1 (n=70) | 0.01225 rad/s | 0.00547 rad/s (-55%) | 71.8 m | 34.5 m (-52%) |

### methodology-consistent
- result: `False`
- reasoning: The fidelity ladder lists V0-V3 variants but no variant table with shared segment-set/regime-mask declaration is provided to verify methodology consistency across variants.
- evidence:
  > Coefficients fit on a random 60% of segments per platform with scipy.optimize.least_squares; the other 40% are the held-out pool above.

### attribution-coherent
- result: `False`
- value: `None`, threshold_met: `False`
- reasoning: No marginal-improvement column is reported for V1/V2/V3; only total V0->Final drop is given, so attribution sum cannot be reconciled.
- evidence:
  > - V0 - pure KS (baseline in yaw_rate_pred_rads): yr = v*tan(delta)/L.
  > - V1 - linear-tire understeer: yr_ss = v*delta / (L + K_us*v^2).
  > - V2 - steering scale + offset: delta_eff = s*delta_road - delta_0.
  > - V3 - 1st-order yaw lag (tau ~ 50 ms) on yr_ss.

### honest-regression-flagged
- result: `None`
- reasoning: not addressed in report
- evidence: _none_
