# angleA-m4-agent-03

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-4/agent-03/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: yaw-rate RMSE
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: V0 = 0.016127 rad/s
- **final_value**: V4 = 0.014897 rad/s
- **improvement**: 7.6% relative improvement
- **top_contributor**: V1

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `False`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "`yaw_rate_meas_rads` is the **measured** truth channel decoded from the rlog gyr…" |
| contract-acknowledged | binary | True | None | "Speed-known contract: `v` and `δ` are **clamped** to the measured values in the …" |
| regime-breakdown-present | binary | True | None | "| Variant | Description | RMSE overall | Straight | Steady | Transient | Δ vs pr…" |
| methodology-consistent | binary | True | None | "Methodology: same segment set and same regime mask **held constant across every …" |
| attribution-coherent | numeric | True | True | "Total drop V0→V4 = 0.001230 rad/s; signed Σ of the Δ column = -0.001230; `|Σmarg…" |
| honest-regression-flagged | binary | True | None | "**Regression flagged with cause: stiff prior `C_α` mis-matches Mach-E lateral co…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: The scored channel is explicitly identified as the measured yaw-rate from the rlog gyro, not a clamped or self-predicted channel.
- evidence:
  > `yaw_rate_meas_rads` is the **measured** truth channel decoded from the rlog gyro; it is not predicted and is not clamped.

### contract-acknowledged
- result: `True`
- reasoning: Methodology section explicitly states which channels are clamped to truth (v, δ) and which are predicted (yaw_rate).
- evidence:
  > Speed-known contract: `v` and `δ` are **clamped** to the measured values in the KS integrator. The **predicted** quantity under test is `yaw_rate_pred_rads` (V0) and its V1–V4 re-predictions.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table includes per-regime RMSE columns for Straight, Steady, and Transient regimes alongside overall.
- evidence:
  > | Variant | Description | RMSE overall | Straight | Steady | Transient | Δ vs prev |

### methodology-consistent
- result: `True`
- reasoning: Explicit declaration that segment set and regime mask are fixed across all variants.
- evidence:
  > Methodology: same segment set and same regime mask **held constant across every variant row**.

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Marginal RMSE drops sum exactly to the total drop, ratio ≈ 0.000, well under 0.15 threshold.
- evidence:
  > Total drop V0→V4 = 0.001230 rad/s; signed Σ of the Δ column = -0.001230; `|Σmarg − total|/total ≈ 0.000` (well under the 15% coherence threshold).

### honest-regression-flagged
- result: `True`
- reasoning: V2 regression is explicitly flagged with a physical cause (stiff prior C_α values mismatched to Mach-E tyre compliance).
- evidence:
  > **Regression flagged with cause: stiff prior `C_α` mis-matches Mach-E lateral compliance.**
