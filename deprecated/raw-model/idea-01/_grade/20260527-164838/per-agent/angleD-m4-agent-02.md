# angleD-m4-agent-02

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-4/agent-02/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: Lateral yaw-rate RMSE on 12 Ford Mustang Mach-E segments
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: V0 = 0.01403 rad/s
- **final_value**: V2 = 0.00825 rad/s
- **improvement**: 41 % reduction
- **top_contributor**: V1 KS recal + yaw-bias

## Honesty flags
- **declared_limitations**: `2`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "`yaw_rate_meas_rads` is **measured** truth (Ford party-DBC yaw gyro)." |
| contract-acknowledged | binary | True | None | "`v` and `δ` are **clamped to measured** under the speed-known contract; speed/st…" |
| regime-breakdown-present | binary | True | None | "| variant | overall | straight | steady | transient |" |
| methodology-consistent | binary | True | None | "Attribution: strict marginal, fixed order V0→V1→V2→V3→V4."; "Lateral yaw-rate RMSE on 12 Ford Mustang Mach-E segments" |
| attribution-coherent | numeric | True | True | "Sum of marginals 0.004031 = total drop 0.004031 (within 15 %, in fact identical)…" |
| honest-regression-flagged | binary | True | None | "V2→V3: **+0.00014 rad/s — regression.** Fitted Cα = (150000, 150000) N/rad. Thes…"; "V3→V4: **+0.00160 rad/s — regression.** Out-of-fold Ridge on `[v, |a_y|, |δ|, si…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Report names the scored channel and identifies it as measured, citing the Ford party-DBC yaw gyro source.
- evidence:
  > `yaw_rate_meas_rads` is **measured** truth (Ford party-DBC yaw gyro).

### contract-acknowledged
- result: `True`
- reasoning: Explicit clamped-vs-predicted statement: v and δ are clamped, yaw_rate is the scored (predicted) channel.
- evidence:
  > `v` and `δ` are **clamped to measured** under the speed-known contract; speed/steering-state agreement is scope, not metric.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table breaks out RMSE per regime (straight / steady / transient) in addition to overall.
- evidence:
  > | variant | overall | straight | steady | transient |

### methodology-consistent
- result: `True`
- reasoning: Same 12-segment set, same per-regime mask, and same RMSE metric used across every variant in the ladder table.
- evidence:
  > Attribution: strict marginal, fixed order V0→V1→V2→V3→V4.
  > Lateral yaw-rate RMSE on 12 Ford Mustang Mach-E segments

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Sum of marginal drops exactly equals total drop, so |Σ−total|/total = 0, well under 0.15 threshold.
- evidence:
  > Sum of marginals 0.004031 = total drop 0.004031 (within 15 %, in fact identical).

### honest-regression-flagged
- result: `True`
- reasoning: V3 and V4 are explicitly flagged as regressions with physical/mechanical causes (optimizer no-op, failure to generalise across segments).
- evidence:
  > V2→V3: **+0.00014 rad/s — regression.** Fitted Cα = (150000, 150000) N/rad. These are exactly the L-BFGS-B initial guesses
  > V3→V4: **+0.00160 rad/s — regression.** Out-of-fold Ridge on `[v, |a_y|, |δ|, sign(δ̇)]` does not generalise across these 12 segments
