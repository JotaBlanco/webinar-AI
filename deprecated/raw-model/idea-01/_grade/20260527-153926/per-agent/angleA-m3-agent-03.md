# angleA-m3-agent-03

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-3/agent-03/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: yaw-rate RMSE in rad/s
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: V0 = 0.01613
- **final_value**: V1 = 0.01469 rad/s
- **improvement**: 8.9% reduction
- **top_contributor**: V1 KS recalibrated (canonical L) + per-segment yaw-gyro bias on straights

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `False`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "`yaw_rate_meas_rads` is the **measured** Ford CAN/IMU truth channel — not a pred…" |
| contract-acknowledged | binary | True | None | "Under the speed-known lateral-only contract, `v_mps` and `delta_road_rad` are **…" |
| regime-breakdown-present | binary | True | None | "| Variant | Description | Overall | Straight | Steady | Transient | Marginal Δ o…" |
| methodology-consistent | binary | True | None | "Regime mask (held constant): straight `|δ|<0.01`, steady `|δ|≥0.01 ∧ |dδ/dt|<0.0…" |
| attribution-coherent | numeric | True | True | "**Strict marginal**, fixed order V0→V1→V2→V3→V4. Sum of marginals: `-0.00144 + 0…" |
| honest-regression-flagged | binary | True | None | "**V2 and V3 are regressions.** Physical cause: openpilot's prior cornering stiff…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Scored channel is named and explicitly identified as the measured Ford CAN/IMU truth channel.
- evidence:
  > `yaw_rate_meas_rads` is the **measured** Ford CAN/IMU truth channel — not a prediction, not a self-consistency replay.

### contract-acknowledged
- result: `True`
- reasoning: Explicit clamped-vs-predicted statement under the lateral-only contract.
- evidence:
  > Under the speed-known lateral-only contract, `v_mps` and `delta_road_rad` are **clamped** to measurement at every integrator step; the **predicted** quantity under test is `yaw_rate_pred_rads`.

### regime-breakdown-present
- result: `True`
- reasoning: Variant ladder table breaks RMSE out by Straight / Steady / Transient regime.
- evidence:
  > | Variant | Description | Overall | Straight | Steady | Transient | Marginal Δ overall |

### methodology-consistent
- result: `True`
- reasoning: A single fixed regime mask and the same RMSE metric are declared and applied across all variants.
- evidence:
  > Regime mask (held constant): straight `|δ|<0.01`, steady `|δ|≥0.01 ∧ |dδ/dt|<0.05`, transient `|δ|≥0.01 ∧ |dδ/dt|≥0.05`. Counts: 785 093 / 106 978 / 21 555.

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Sum of marginal drops equals total drop exactly; mismatch ratio is ~0, well under the 0.15 threshold.
- evidence:
  > **Strict marginal**, fixed order V0→V1→V2→V3→V4. Sum of marginals: `-0.00144 + 0.00082 + 0.00013 - 0.00023 = -0.00072`. Total V0→V4: `0.01613 - 0.01541 = 0.00072`. **Match exact** (<1% of total drop, well under 15% guard).

### honest-regression-flagged
- result: `True`
- reasoning: Regressions V2 and V3 are explicitly flagged and given a physical cause (stiffness/slip mismatch).
- evidence:
  > **V2 and V3 are regressions.** Physical cause: openpilot's prior cornering stiffnesses (286.6k front / 355.9k rear) characterise a stiffer-than-reality tyre, so `K_us` magnitude is too small (slight oversteer/near-neutral) — at moderate `v` the ST yaw-rate gain ends up *larger* than reality, overshooting `ψ̇_meas`.
