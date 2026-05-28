# angleA-m2-agent-05

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-2/agent-05/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: lateral residual `yaw_rate_pred − yaw_rate_meas`
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: V0 = 0.01613
- **final_value**: V4 = 0.01035
- **improvement**: 35.8% reduction
- **top_contributor**: V2 + α re-fit

## Honesty flags
- **declared_limitations**: `2`
- **named_data_gap_or_missing_truth_channel**: `False`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "`yaw_rate_meas_rads` and `a_lat_meas_mps2` are **measured truth** channels (Ford…" |
| contract-acknowledged | binary | True | None | "**Speed-known contract honoured.** `v_mps` and `delta_road_rad` are **clamped** …" |
| regime-breakdown-present | binary | True | None | "| Variant | RMSE (rad/s) | Straight | Steady | Transient | Marginal Δ | Note |" |
| methodology-consistent | binary | True | None | "**Regimes** (fixed across all variants): `|a_y|≥1.0` ∧ `|jerk|≥1.0` → transient;…" |
| attribution-coherent | numeric | True | True | "**Total drop:** 0.00578 rad/s = sum of marginals 0.00577 (rounding)." |
| honest-regression-flagged | binary | True | None | "**No regressions** — every variant strictly reduced RMSE in every regime." |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Report explicitly names the scored channel as measured and cites the Ford IMU source.
- evidence:
  > `yaw_rate_meas_rads` and `a_lat_meas_mps2` are **measured truth** channels (Ford IMU decoded by the adapter), not predictions or self-consistency.

### contract-acknowledged
- result: `True`
- reasoning: Report explicitly states which channels are clamped vs predicted.
- evidence:
  > **Speed-known contract honoured.** `v_mps` and `delta_road_rad` are **clamped** inputs. `yaw_rate_pred_rads` and `a_y_pred_mps2` are the only predicted channels.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table breaks out RMSE per regime (Straight, Steady, Transient).
- evidence:
  > | Variant | RMSE (rad/s) | Straight | Steady | Transient | Marginal Δ | Note |

### methodology-consistent
- result: `True`
- reasoning: Same regime definitions and metric (RMSE rad/s) used across every variant row.
- evidence:
  > **Regimes** (fixed across all variants): `|a_y|≥1.0` ∧ `|jerk|≥1.0` → transient; cornering otherwise; straight = neither.

### attribution-coherent
- result: `True`
- value: `0.0017`, threshold_met: `True`
- reasoning: Sum of marginals (0.00577) reconciles with total drop (0.00578); |diff|/total ≈ 0.0017, well under 0.15.
- evidence:
  > **Total drop:** 0.00578 rad/s = sum of marginals 0.00577 (rounding).

### honest-regression-flagged
- result: `True`
- reasoning: Report includes an explicit no-regressions statement, satisfying the vacuous-case clause.
- evidence:
  > **No regressions** — every variant strictly reduced RMSE in every regime.
