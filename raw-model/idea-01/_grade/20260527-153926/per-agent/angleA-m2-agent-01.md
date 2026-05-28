# angleA-m2-agent-01

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-2/agent-01/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: Overall yaw-rate RMSE
- **platform**: Ford (Mach-E MK1 + F-150 Lightning MK1), 545 segments total
- **baseline_value**: 0.01804 rad/s (V0)
- **final_value**: 0.01568 rad/s (V4)
- **improvement**: 13.1% reduction
- **top_contributor**: V4 understeer

## Honesty flags
- **declared_limitations**: `2`
- **named_data_gap_or_missing_truth_channel**: `False`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "The `yaw_rate_meas_rads` and `a_lat_meas_mps2` columns are **measured truth** de…" |
| contract-acknowledged | binary | True | None | "`v_mps` and `delta_road_rad` are **clamped** inputs in every variant; the KS int…" |
| regime-breakdown-present | binary | True | None | "| Variant | Straight | Steady | Transient | Overall | Δ vs prior | Description |" |
| methodology-consistent | binary | True | None | "Same Ford segment set, same regime mask, marginal-drop accounting on global RMSE…" |
| attribution-coherent | numeric | True | True | "Marginal drops sum to 0.00236, matching total V0−V4." |
| honest-regression-flagged | binary | True | None | "**No regressions observed.**" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Agent explicitly names the scored channel and identifies it as measured truth from rlog CAN.
- evidence:
  > The `yaw_rate_meas_rads` and `a_lat_meas_mps2` columns are **measured truth** decoded from rlog CAN, not predictions or self-consistency.

### contract-acknowledged
- result: `True`
- reasoning: Explicit clamped-vs-predicted statement is in the methodology header.
- evidence:
  > `v_mps` and `delta_road_rad` are **clamped** inputs in every variant; the KS integrator's own `v`/`δ` state updates are overwritten by measurement each step. The **predicted** channel under test is `yaw_rate_pred_rads`.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table breaks error out by straight/steady/transient regimes in addition to overall.
- evidence:
  > | Variant | Straight | Steady | Transient | Overall | Δ vs prior | Description |

### methodology-consistent
- result: `True`
- reasoning: Table caption declares a fixed segment set and regime mask shared across all variants.
- evidence:
  > Same Ford segment set, same regime mask, marginal-drop accounting on global RMSE.

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Marginal drops (0.00051+0.00001+0.00018+0.00165=0.00235) reconcile with total V0-V4 drop (0.01804-0.01568=0.00236); |Σ − total|/total ≈ 0.004, well under 0.15.
- evidence:
  > Marginal drops sum to 0.00236, matching total V0−V4.

### honest-regression-flagged
- result: `True`
- reasoning: Explicit 'no regressions observed' statement is present in the Notes section.
- evidence:
  > **No regressions observed.**
