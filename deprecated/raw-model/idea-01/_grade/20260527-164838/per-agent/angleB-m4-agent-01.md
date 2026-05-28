# angleB-m4-agent-01

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-4/agent-01/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: yaw-rate RMSE (rad/s)
- **platform**: Ford Mustang Mach-E MK1
- **baseline_value**: 0.01214
- **final_value**: 0.01055
- **improvement**: -13% overall RMSE (0.01214 → 0.01055 rad/s)
- **top_contributor**: V1 per-segment IMU yaw-gyro bias removal

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "Ford Mustang Mach-E MK1 (the only platform with truth ψ̇ and a_y; Tesla has no I…" |
| contract-acknowledged | binary | True | None | "`v` and `δ` clamped to measured; residual under test is `yaw_rate_pred_rads − ya…" |
| regime-breakdown-present | binary | True | None | "| # | Variant | overall | straight | steady | transient | marginal Δ overall |" |
| methodology-consistent | binary | True | None | "## Variant ladder (same segments, same mask, RMSE rad/s)" |
| attribution-coherent | numeric | True | True | "Marginal drops sum to total V0→V4 (consistency 100%, lock-order strict-marginal)…" |
| honest-regression-flagged | binary | True | None | "| V3 | + linear ST, fit C_α | 0.01550 | 0.00569 | 0.04286 | 0.07162 | +0.00302 (…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: The scored channel is the measured yaw rate (yaw_rate_meas_rads) on the Mach-E platform, which is identified as the only platform with measured truth ψ̇.
- evidence:
  > Ford Mustang Mach-E MK1 (the only platform with truth ψ̇ and a_y; Tesla has no IMU truth). `v` and `δ` clamped to measured; residual under test is `yaw_rate_pred_rads − yaw_rate_meas_rads`.

### contract-acknowledged
- result: `True`
- reasoning: Explicit clamped-vs-predicted statement: v and δ are clamped to measured, yaw_rate is predicted and compared to measured.
- evidence:
  > `v` and `δ` clamped to measured; residual under test is `yaw_rate_pred_rads − yaw_rate_meas_rads`.

### regime-breakdown-present
- result: `True`
- reasoning: The variant table breaks RMSE out by straight / steady / transient regimes alongside overall.
- evidence:
  > | # | Variant | overall | straight | steady | transient | marginal Δ overall |

### methodology-consistent
- result: `True`
- reasoning: The variant table caption declares a fixed segment-set and mask, with RMSE rad/s as the unified metric across all variants.
- evidence:
  > ## Variant ladder (same segments, same mask, RMSE rad/s)

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: The marginal Δ column (-0.00159 + 0.00193 + 0.00302 + -0.00214 = 0.00122) reconciles exactly with the total V0→V4 change (0.01214 → 0.01336 = +0.00122); |Σ−total|/|total| ≈ 0, well under 0.15.
- evidence:
  > Marginal drops sum to total V0→V4 (consistency 100%, lock-order strict-marginal).

### honest-regression-flagged
- result: `True`
- reasoning: Regressions in V2, V3, V4 are explicitly flagged with physical reasons (e.g., C_α pegged at lower bound; openpilot prior K_us shrinks ψ̇ wrong direction).
- evidence:
  > | V3 | + linear ST, fit C_α | 0.01550 | 0.00569 | 0.04286 | 0.07162 | +0.00302 (regress, **C_α pegged at lower bound 50 kN/rad** — linear-ST form is wrong, not just priors) |
