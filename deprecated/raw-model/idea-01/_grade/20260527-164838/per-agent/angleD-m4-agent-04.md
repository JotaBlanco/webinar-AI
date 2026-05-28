# angleD-m4-agent-04

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-4/agent-04/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: Overall RMSE (rad/s)
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.01704
- **final_value**: 0.01635
- **improvement**: −0.00069 rad/s overall, **−0.00433 in the straight regime**
- **top_contributor**: V1

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "`yaw_rate_meas_rads` is the **measured** truth channel from the openpilot rlog I…" |
| contract-acknowledged | binary | True | None | "Operating contract: `v` and `δ` are **clamped to measured** every step (speed-kn…" |
| regime-breakdown-present | binary | True | None | "| V0 | As-is `yaw_rate_resid_rads` baseline | 0.01704 | 0.00913 | 0.03128 | 0.05…" |
| methodology-consistent | binary | True | None | "Segment set: 8 distinct routes under `data/sim/segments/FORD_MUSTANG_MACH_E_MK1/…" |
| attribution-coherent | numeric | True | True | "Attribution: **strict marginal**, fixed order V0→V1→V2→V3→V4. Marginal drops sum…" |
| honest-regression-flagged | binary | True | None | "**V2 (prior Cα)**: linear-ST with stiff prior under-predicts yaw rate in corneri…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Names the scored channel as measured and cites the openpilot rlog IMU as the source.
- evidence:
  > `yaw_rate_meas_rads` is the **measured** truth channel from the openpilot rlog IMU.

### contract-acknowledged
- result: `True`
- reasoning: Explicitly states which channels are clamped to measured vs which are predicted (yaw rate is the scored predicted channel).
- evidence:
  > Operating contract: `v` and `δ` are **clamped to measured** every step (speed-known, lateral-only). Speed-state agreement is zero by construction and is not the metric.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table breaks out RMSE by Straight/Steady/Transient regimes for every variant.
- evidence:
  > | V0 | As-is `yaw_rate_resid_rads` baseline | 0.01704 | 0.00913 | 0.03128 | 0.05246 | — | baseline |

### methodology-consistent
- result: `True`
- reasoning: Single fixed segment set and regime split declared upfront, with same RMSE metric and same regime columns reused across every variant in the ladder table.
- evidence:
  > Segment set: 8 distinct routes under `data/sim/segments/FORD_MUSTANG_MACH_E_MK1/` (first sim.csv per route), 23,189 rows total. Regime split: 19,581 straight / 2,723 steady / 885 transient.

### attribution-coherent
- result: `True`
- value: `0.01`, threshold_met: `True`
- reasoning: Marginal column present (+0.00069, -0.00416, -0.00016, -0.00684 sums to -0.01047; V0-V4 total = 0.01704-0.02751 = -0.01047), reconcilable to within <1% — well under the 0.15 threshold.
- evidence:
  > Attribution: **strict marginal**, fixed order V0→V1→V2→V3→V4. Marginal drops sum to the total V0→V4 drop within < 1% — accounting is consistent.

### honest-regression-flagged
- result: `True`
- reasoning: Variant table marks V2/V3/V4 as 'regression' and the narrative gives a physical cause for each.
- evidence:
  > **V2 (prior Cα)**: linear-ST with stiff prior under-predicts yaw rate in cornering. Cornering RMSE in steady regime jumps 0.031 → 0.043, transient 0.052 → 0.071.
