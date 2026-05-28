# angleE-m2-agent-04

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-2/agent-04/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: Lateral residual `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` is the sole metric.
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.01613
- **final_value**: 0.01469
- **improvement**: +0.00144 improvement (8.9% relative)
- **top_contributor**: V1 (KS recalib + per-segment yaw-gyro bias)

## Honesty flags
- **declared_limitations**: `5`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "`yaw_rate_meas_rads` is measured truth from the rlog IMU (Ford-only — no Tesla m…" |
| contract-acknowledged | binary | True | None | "Speed `v` and steering `δ` are clamped to measured (`clamp_v_to_measured=True`, …" |
| regime-breakdown-present | binary | True | None | "| variant | overall | straight | steady | transient |" |
| methodology-consistent | binary | True | None | "Lateral residual `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads`…"; "| variant | overall | straight | steady | transient |" |
| attribution-coherent | numeric | True | True | "Sum of marginals (−0.00050) equals total V0→V3 drop (−0.00050). Variants are not…" |
| honest-regression-flagged | binary | True | None | "V1→V2 marginal: **−0.00184 regression** (every regime worsens). The understeer-c…"; "V2 and V3 both regress vs V0 in **every** regime (overall, straight, steady, tra…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Agent explicitly names the scored channel as measured from the rlog IMU on the Ford platform.
- evidence:
  > `yaw_rate_meas_rads` is measured truth from the rlog IMU (Ford-only — no Tesla measured yaw available).

### contract-acknowledged
- result: `True`
- reasoning: Methodology section explicitly states which channels are clamped to measured and which is predicted/scored.
- evidence:
  > Speed `v` and steering `δ` are clamped to measured (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Lateral residual `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` is the sole metric.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table presents per-regime columns (straight, steady, transient) in addition to overall.
- evidence:
  > | variant | overall | straight | steady | transient |

### methodology-consistent
- result: `True`
- reasoning: Same metric definition and same regime segmentation (straight/steady/transient) applied to every variant in the ladder.
- evidence:
  > Lateral residual `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` is the sole metric.
  > | variant | overall | straight | steady | transient |

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Agent reports marginal sum equals total drop exactly, giving |Σ marginals − total| / |total| = 0, well under 0.15.
- evidence:
  > Sum of marginals (−0.00050) equals total V0→V3 drop (−0.00050). Variants are not compounded — V2/V3 are computed from raw KS form, not from V1 — so the equality is bookkeeping, not a coincidence.

### honest-regression-flagged
- result: `True`
- reasoning: Regressions are explicitly identified with physical reasoning (understeer correction shrinks yaw; bias correction not propagated; flat loss surface at x0).
- evidence:
  > V1→V2 marginal: **−0.00184 regression** (every regime worsens). The understeer-corrected ST `psi = v·δ / (L·(1 + K_us·v²))` returns smaller yaw than KS, and the bias correction from V1 is not carried forward by design.
  > V2 and V3 both regress vs V0 in **every** regime (overall, straight, steady, transient).
