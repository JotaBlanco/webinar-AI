# angleA-m4-agent-02

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-4/agent-02/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: RMSE overall (rad/s)
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.012144
- **final_value**: 0.009608
- **improvement**: ~21% overall reduction; ~60% reduction on the straight regime
- **top_contributor**: V4

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "Scored channel: **`yaw_rate_meas_rads`** is the **measured** truth (IMU yaw gyro…" |
| contract-acknowledged | binary | True | None | "Speed-known contract: `v_mps` and `delta_road_rad` are **clamped** to measuremen…" |
| regime-breakdown-present | binary | True | None | "| Variant | Description | RMSE overall (rad/s) | Straight | Steady | Transient |…" |
| methodology-consistent | binary | True | None | "60 Mach-E segments / 173 940 rows / 50 Hz. Same **segment set** and same **regim…" |
| attribution-coherent | numeric | True | True | "Attribution scheme: **strict marginal**, fixed order V0→V1→V2→V3→V4. Σmarginal =…" |
| honest-regression-flagged | binary | True | None | "**V2 worsened V1 by +1.93 mrad/s.** Cause: openpilot prior `C_α` is stiffer than…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Report names the scored channel and explicitly identifies it as the measured IMU yaw gyro, citing rlog as source.
- evidence:
  > Scored channel: **`yaw_rate_meas_rads`** is the **measured** truth (IMU yaw gyro decoded from rlog). Predictions come from each variant rung.

### contract-acknowledged
- result: `True`
- reasoning: Methodology contains an explicit clamped-vs-predicted statement naming which channels are clamped and which are predicted.
- evidence:
  > Speed-known contract: `v_mps` and `delta_road_rad` are **clamped** to measurement at every step; only `yaw_rate_pred_rads` / `a_y_pred_mps2` are **predicted**.

### regime-breakdown-present
- result: `True`
- reasoning: Variant ladder table breaks RMSE into straight / steady / transient columns per variant.
- evidence:
  > | Variant | Description | RMSE overall (rad/s) | Straight | Steady | Transient | Δ vs prev (rad/s) |

### methodology-consistent
- result: `True`
- reasoning: Methodology explicitly fixes the segment set and regime mask across every variant on the ladder.
- evidence:
  > 60 Mach-E segments / 173 940 rows / 50 Hz. Same **segment set** and same **regime mask** **held constant** across every row.

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Marginal column and total drop are both present and reconcile exactly (0.000 vs threshold <0.15).
- evidence:
  > Attribution scheme: **strict marginal**, fixed order V0→V1→V2→V3→V4. Σmarginal = 0.002536, total V0→V4 = 0.002536, `|Σ − total|/total = 0.000`.

### honest-regression-flagged
- result: `True`
- reasoning: Regression flags section names V2 and V3 as regressions and gives a physical cause for each.
- evidence:
  > **V2 worsened V1 by +1.93 mrad/s.** Cause: openpilot prior `C_α` is stiffer than the Mach-E tyres under the segment-set's operating envelope.
