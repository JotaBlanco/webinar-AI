# angleC-m2-agent-05

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-2/agent-05/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: test-only RMSE of yaw-rate residual (rad/s)
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.01613
- **final_value**: 0.01561
- **improvement**: V2 alone delivers +3.3% net
- **top_contributor**: V2 steer-gain k = 1.0843

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "`yaw_rate_meas_rads` is the measured truth channel decoded from the rlog IMU; Te…" |
| contract-acknowledged | binary | True | None | "`v` and `δ` are **clamped to measured**, not predicted. Only lateral states (ψ, …" |
| regime-breakdown-present | binary | True | None | "| Variant | all | straight | steady-corner | transient-corner |" |
| methodology-consistent | binary | True | None | "Same segment set, same regime masks across rows (straight: |ψ̇|<0.03; transient:…" |
| attribution-coherent | numeric | True | True | "V1 bias removal: Δ = -0.08% (bias is ~0; ISO sign already correct upstream)."; "V2 steer-gain: Δ = +3.29% improvement (transient-corner RMSE drops 17%: 0.0483 →…"; "V3 lag align: Δ = -3.92% (regression)."; "Net V0 → V3: -0.72% overall." |
| honest-regression-flagged | binary | True | None | "**V3 lag-align (+40 ms) regresses.** Cause: Mach-E KS prediction is in-phase wit…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Agent names the scored channel and explicitly identifies it as measured, citing the rlog IMU source.
- evidence:
  > `yaw_rate_meas_rads` is the measured truth channel decoded from the rlog IMU; Tesla excluded per AGENTS.md rule 4 (no decodable yaw-rate truth).

### contract-acknowledged
- result: `True`
- reasoning: Explicit clamped-vs-predicted statement is given under Operating contract.
- evidence:
  > `v` and `δ` are **clamped to measured**, not predicted. Only lateral states (ψ, ψ̇, a_y) are under test.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table provides per-regime RMSE columns (straight, steady-corner, transient-corner) in addition to aggregate.
- evidence:
  > | Variant | all | straight | steady-corner | transient-corner |

### methodology-consistent
- result: `True`
- reasoning: Agent explicitly declares the segment set and regime masks are fixed across all variant rows.
- evidence:
  > Same segment set, same regime masks across rows (straight: |ψ̇|<0.03; transient: cornering with |dψ̇/dt|≥0.10).

### attribution-coherent
- result: `True`
- value: `0.05`, threshold_met: `True`
- reasoning: Sum of marginal deltas (-0.08 + 3.29 - 3.92 = -0.71%) reconciles closely with net -0.72%; |Σ − total|/|total| ≈ 0.014, well under 0.15.
- evidence:
  > V1 bias removal: Δ = -0.08% (bias is ~0; ISO sign already correct upstream).
  > V2 steer-gain: Δ = +3.29% improvement (transient-corner RMSE drops 17%: 0.0483 → 0.0401).
  > V3 lag align: Δ = -3.92% (regression).
  > Net V0 → V3: -0.72% overall.

### honest-regression-flagged
- result: `True`
- reasoning: V3 regression is explicitly flagged with a physical-cause explanation about phase vs amplitude error.
- evidence:
  > **V3 lag-align (+40 ms) regresses.** Cause: Mach-E KS prediction is in-phase with measured ψ̇ once V2's gain correction is applied; the residual transient-cornering error is amplitude, not timing.
