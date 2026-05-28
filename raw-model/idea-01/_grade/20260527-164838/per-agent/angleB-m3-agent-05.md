# angleB-m3-agent-05

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-3/agent-05/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: RMSE of `yaw_rate_pred − yaw_rate_meas_rads`
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.01316
- **final_value**: 0.01166
- **improvement**: Total drop V0→V3 = -0.00150 rad/s (≈11% of V0)
- **top_contributor**: V1 + per-segment straight-line bias (IMU gyro offset)

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "Predicted channel under test is `yaw_rate_pred_rads`. Metric is RMSE of `yaw_rat…"; "Platform: `FORD_MUSTANG_MACH_E_MK1` (Ford required for lateral truth; Tesla has …" |
| contract-acknowledged | binary | True | None | "**Clamped vs predicted:** `v` and `δ_road` are clamped to measurement (`clamp_v_…" |
| regime-breakdown-present | binary | True | None | "| Variant | Description | RMSE all | straight | steady | transient | Marginal dr…" |
| methodology-consistent | binary | True | None | "## Variant ladder (cumulative, same segment set, same regime mask)" |
| attribution-coherent | numeric | True | True | "Total drop V0→V3 = -0.00150 rad/s (≈11% of V0). Sum of marginals = -0.00150 — ex…" |
| honest-regression-flagged | binary | True | None | "V2 regresses against V1 on every cornering regime (steady +19%, transient +18%).…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Scores predicted yaw rate against measured yaw rate on the Ford platform, explicitly noting Ford is required because Tesla lacks the measurement.
- evidence:
  > Predicted channel under test is `yaw_rate_pred_rads`. Metric is RMSE of `yaw_rate_pred − yaw_rate_meas_rads`.
  > Platform: `FORD_MUSTANG_MACH_E_MK1` (Ford required for lateral truth; Tesla has no yaw-rate measurement).

### contract-acknowledged
- result: `True`
- reasoning: Explicit clamped-vs-predicted statement naming which channels are clamped to truth and which is predicted.
- evidence:
  > **Clamped vs predicted:** `v` and `δ_road` are clamped to measurement (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Predicted channel under test is `yaw_rate_pred_rads`.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table includes per-regime columns for straight, steady, and transient RMSE.
- evidence:
  > | Variant | Description | RMSE all | straight | steady | transient | Marginal drop |

### methodology-consistent
- result: `True`
- reasoning: Header of variant ladder explicitly declares fixed segment set and regime mask across all variants.
- evidence:
  > ## Variant ladder (cumulative, same segment set, same regime mask)

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Sum of marginal RMSE drops equals total drop exactly, so |Σ marginals − total|/|total| = 0 < 0.15.
- evidence:
  > Total drop V0→V3 = -0.00150 rad/s (≈11% of V0). Sum of marginals = -0.00150 — exact, no double-counting.

### honest-regression-flagged
- result: `True`
- reasoning: V2 regression explicitly flagged with a physical cause (prior stiffnesses producing too-large steady-state yaw gain).
- evidence:
  > V2 regresses against V1 on every cornering regime (steady +19%, transient +18%). The prior stiffnesses make steady-state yaw gain too large at the speeds in this fleet.
