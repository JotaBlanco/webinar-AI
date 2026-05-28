# angleA-m3-agent-01

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-3/agent-01/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: RMSE on `yaw_rate_resid_rads` (rad/s)
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.01190
- **final_value**: 0.01003
- **improvement**: 15.7% improvement vs V0
- **top_contributor**: V4 Ridge residual learner on V3, LOSO

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `False`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "`yaw_rate_meas_rads` is **measured** truth decoded from the rlog IMU — not a pre…" |
| contract-acknowledged | binary | True | None | "**Speed-known contract**: `v_mps` and `delta_road_rad` **clamped** to measuremen…" |
| regime-breakdown-present | binary | True | None | "| Variant | Overall | Straight | Steady | Transient | Marginal drop |" |
| methodology-consistent | binary | True | None | "**Regime mask** (constant): straight `|δ|<0.01`; steady `|δ|≥0.01 ∧ |δ̇|<0.05`; …" |
| attribution-coherent | numeric | True | True | "Total drop V0→V4 = 0.00187 rad/s. Sum of marginals = 0.00187 rad/s." |
| honest-regression-flagged | binary | True | None | "**V2 is a regression vs V1.** Openpilot's prior C_α (286k/356k N/rad) is stiffer…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Agent explicitly names the scored channel as measured and cites the rlog IMU as source.
- evidence:
  > `yaw_rate_meas_rads` is **measured** truth decoded from the rlog IMU — not a prediction, not the integrator's own state.

### contract-acknowledged
- result: `True`
- reasoning: Methodology explicitly states which channels are clamped and which is predicted.
- evidence:
  > **Speed-known contract**: `v_mps` and `delta_road_rad` **clamped** to measurement at every step; the **predicted** channel is `yaw_rate_pred_rads`.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table breaks RMSE down by Straight/Steady/Transient regimes alongside the overall column.
- evidence:
  > | Variant | Overall | Straight | Steady | Transient | Marginal drop |

### methodology-consistent
- result: `True`
- reasoning: A single fixed regime mask and a single metric (RMSE on yaw_rate_resid_rads) are declared and used across all variants in the ladder.
- evidence:
  > **Regime mask** (constant): straight `|δ|<0.01`; steady `|δ|≥0.01 ∧ |δ̇|<0.05`; transient `|δ|≥0.01 ∧ |δ̇|≥0.05`. Counts: 211 404 / 17 627 / 2 895.

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Sum of marginal drops equals the total drop exactly, so |Σ marginals − total| / total = 0, well under the 0.15 threshold.
- evidence:
  > Total drop V0→V4 = 0.00187 rad/s. Sum of marginals = 0.00187 rad/s.

### honest-regression-flagged
- result: `True`
- reasoning: Agent calls out V2 as a regression and gives a physical cause (overly stiff prior C_α producing under-rotation).
- evidence:
  > **V2 is a regression vs V1.** Openpilot's prior C_α (286k/356k N/rad) is stiffer than these Mach-E tyres behave, so ST under-rotates at meaningful slip, worsening cornering by ≈30–40% relative to V1.
