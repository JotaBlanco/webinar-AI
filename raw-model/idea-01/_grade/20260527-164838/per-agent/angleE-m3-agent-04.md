# angleE-m3-agent-04

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-3/agent-04/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: RMSE(yaw_rate_pred_rads − yaw_rate_meas_rads)
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.016127
- **final_value**: 0.016635
- **improvement**: −0.001434 rad/s overall RMSE (≈ −8.9%)
- **top_contributor**: V1 KS recalibrated (canonical L + per-segment bias)

## Honesty flags
- **declared_limitations**: `4`
- **named_data_gap_or_missing_truth_channel**: `False`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "`yaw_rate_meas_rads` from the Ford `sim.csv` is the measured truth channel." |
| contract-acknowledged | binary | True | None | "`v_mps` and `delta_road_rad` are clamped to measured in KS, by harness contract." |
| regime-breakdown-present | binary | True | None | "| V0 raw residual | 0.016127 | 0.008768 | 0.031733 | 0.056797 | — | baseline |" |
| methodology-consistent | binary | True | None | "Rows: 913,626 across the Mach-E segment set. Regime split: straight 785,093 / st…" |
| attribution-coherent | numeric | True | True | "Sum of marginal drops: **−0.000508 rad/s** — exact (within 0.0% of total, well i…" |
| honest-regression-flagged | binary | True | None | "**V1→V2 (overall +0.001836)** — the steady-state linear-bicycle gain `v·δ / (L·(…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Report explicitly names the scored channel and identifies it as measured, citing the dataset source.
- evidence:
  > `yaw_rate_meas_rads` from the Ford `sim.csv` is the measured truth channel.

### contract-acknowledged
- result: `True`
- reasoning: Explicit clamped-vs-predicted statement in the Operating contract section identifying clamped inputs and the predicted yaw rate channel.
- evidence:
  > `v_mps` and `delta_road_rad` are clamped to measured in KS, by harness contract.

### regime-breakdown-present
- result: `True`
- reasoning: Variant ladder table breaks out RMSE per regime (straight / steady / transient) for every variant.
- evidence:
  > | V0 raw residual | 0.016127 | 0.008768 | 0.031733 | 0.056797 | — | baseline |

### methodology-consistent
- result: `True`
- reasoning: A fixed segment set and regime split are declared and the same metric (RMSE of yaw-rate residual) is used across every variant.
- evidence:
  > Rows: 913,626 across the Mach-E segment set. Regime split: straight 785,093 / steady 106,978 / transient 21,555.

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Marginal drops sum exactly to total drop; reconciliation error 0.0%, well below 0.15.
- evidence:
  > Sum of marginal drops: **−0.000508 rad/s** — exact (within 0.0% of total, well inside the 15% reconciliation bound).

### honest-regression-flagged
- result: `True`
- reasoning: V2 and V3 regressions are explicitly labelled as regressions in the variant table and given physical causes (gain underprediction, missing bias removal, flat loss surface).
- evidence:
  > **V1→V2 (overall +0.001836)** — the steady-state linear-bicycle gain `v·δ / (L·(1+K_us·v²))` underpredicts yaw rate vs the simpler KS `v·tan(δ)/L`.
