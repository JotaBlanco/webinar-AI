# angleA-m4-agent-01

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-4/agent-01/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: RMSE overall (rad/s)
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.01394
- **final_value**: 0.01120
- **improvement**: −19.6%
- **top_contributor**: V4

## Honesty flags
- **declared_limitations**: `2`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "**Scored channel.** `yaw_rate_meas_rads` is the **measured** truth (IMU yaw gyro…" |
| contract-acknowledged | binary | True | None | "Operating under the speed-known / lateral-only contract: `v_mps` and `delta_road…" |
| regime-breakdown-present | binary | True | None | "| Variant | Description | RMSE overall (rad/s) | Straight | Steady | Transient |…" |
| methodology-consistent | binary | True | None | "**Methodology consistency.** Segment set (same 40 sim.csv files) and regime mask…" |
| attribution-coherent | numeric | True | True | "**Attribution accounting.** Strict marginal, fixed order V0→V1→V2→V3→V4. By cons…"; "Attribution `|Σmarg − total|/total ≈ 0` (consecutive-difference accounting)." |
| honest-regression-flagged | binary | True | None | "**V2 worsened V1 by +1.93 mrad/s.** Cause: stiffer-than-real prior `C_α` over-pr…"; "**V3 worsened V1 by +1.62 mrad/s** (even after `C_α` fit). Cause: linear-ST func…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Report explicitly names the scored channel as measured IMU yaw rate decoded from rlog.
- evidence:
  > **Scored channel.** `yaw_rate_meas_rads` is the **measured** truth (IMU yaw gyro decoded from rlog). All variants score `pred − measured` RMSE against this same column.

### contract-acknowledged
- result: `True`
- reasoning: Methodology explicitly states which channels are clamped vs predicted.
- evidence:
  > Operating under the speed-known / lateral-only contract: `v_mps` and `delta_road_rad` are **clamped** to measurement at every integration step. The integrator's `v`/`δ` updates are overwritten. The **predicted** channels are `yaw_rate_pred_rads` (V0) and recomputed yaw-rate from each variant (V1..V4).

### regime-breakdown-present
- result: `True`
- reasoning: Variant table includes per-regime columns (Straight/Steady/Transient) for every variant.
- evidence:
  > | Variant | Description | RMSE overall (rad/s) | Straight | Steady | Transient | Δ marginal (rad/s) |

### methodology-consistent
- result: `True`
- reasoning: Explicit statement that segment set and regime mask are fixed across all variants.
- evidence:
  > **Methodology consistency.** Segment set (same 40 sim.csv files) and regime mask **held constant across every row**.

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Sequential marginals sum to total by construction; coherence ratio ≈ 0, well below 0.15 threshold.
- evidence:
  > **Attribution accounting.** Strict marginal, fixed order V0→V1→V2→V3→V4. By construction marginals sum to total drop (attribution coherence ≈ 0%, well inside the 15% budget).
  > Attribution `|Σmarg − total|/total ≈ 0` (consecutive-difference accounting).

### honest-regression-flagged
- result: `True`
- reasoning: Dedicated 'Honest regression flags' section names regressions with physical causes.
- evidence:
  > **V2 worsened V1 by +1.93 mrad/s.** Cause: stiffer-than-real prior `C_α` over-predicts yaw in cornering.
  > **V3 worsened V1 by +1.62 mrad/s** (even after `C_α` fit). Cause: linear-ST functional form cannot represent the non-linear slip; fitting in a wrong model class moves you along a wrong manifold.
