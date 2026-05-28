# angleA-m3-agent-05

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-3/agent-05/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: RMSE of yaw-rate residual, rad/s
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.01190
- **final_value**: 0.00963
- **improvement**: total drop = 19% relative (0.00227 rad/s absolute)
- **top_contributor**: V4 Residual learner on V3 (LOO)

## Honesty flags
- **declared_limitations**: `2`
- **named_data_gap_or_missing_truth_channel**: `False`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "`yaw_rate_meas_rads` is the **measured** yaw-rate channel from the rlog IMU (not…" |
| contract-acknowledged | binary | True | None | "Speed-known contract: `v_mps` and `delta_road_rad` are **clamped** to measured s…" |
| regime-breakdown-present | binary | True | None | "| Variant | Overall | Straight | Steady cornering | Transient cornering | Margin…" |
| methodology-consistent | binary | True | None | "Segment set: first 80 of 315 Mach-E `sim.csv` files (231 926 rows — 211k straigh…" |
| attribution-coherent | numeric | True | True | "Total drop V0→V4 = **0.00227 rad/s**. Sum of marginals = **0.00228 rad/s** (clos…" |
| honest-regression-flagged | binary | True | None | "**V2 (Linear ST prior)** — overall regression (-0.00161 rad/s). Physical cause: …" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Report explicitly names the scored channel as the measured IMU yaw-rate from rlog.
- evidence:
  > `yaw_rate_meas_rads` is the **measured** yaw-rate channel from the rlog IMU (not predicted, not self-consistency).

### contract-acknowledged
- result: `True`
- reasoning: Explicit clamped-vs-predicted statement identifying v and delta as clamped and yaw_rate as predicted.
- evidence:
  > Speed-known contract: `v_mps` and `delta_road_rad` are **clamped** to measured signals. The integrator's `v`/`δ` updates are overwritten every step. Only quantity under test is `yaw_rate_pred_rads`

### regime-breakdown-present
- result: `True`
- reasoning: Variant table breaks error out by straight, steady cornering, and transient cornering regimes.
- evidence:
  > | Variant | Overall | Straight | Steady cornering | Transient cornering | Marginal Δ overall | Notes |

### methodology-consistent
- result: `True`
- reasoning: Report explicitly states identical segment-set and regime mask across all variants.
- evidence:
  > Segment set: first 80 of 315 Mach-E `sim.csv` files (231 926 rows — 211k straight / 17.6k steady / 2.9k transient). Identical segment-set and identical regime mask for every row.

### attribution-coherent
- result: `True`
- value: `0.0044`, threshold_met: `True`
- reasoning: |0.00228 - 0.00227| / 0.00227 ≈ 0.0044, far below the 0.15 threshold.
- evidence:
  > Total drop V0→V4 = **0.00227 rad/s**. Sum of marginals = **0.00228 rad/s** (closes to within 0.5%, well under 15%).

### honest-regression-flagged
- result: `True`
- reasoning: V2 is flagged as a regression with a physical-cause explanation.
- evidence:
  > **V2 (Linear ST prior)** — overall regression (-0.00161 rad/s). Physical cause: openpilot prior tyre stiffness for the Mach-E is too high for the actual rubber/load combination, so the steady-state gain predicts a smaller yaw rate than measured, biasing all cornering samples positive in residual.
