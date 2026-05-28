# angleD-m3-agent-05

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-3/agent-05/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: RMSE in rad/s, lower is better
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.01575
- **final_value**: 0.01368
- **improvement**: −39.5%
- **top_contributor**: V1 KS + per-seg yaw-gyro bias

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `False`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "`yaw_rate_meas_rads` is **measured** truth from the Ford party DBC in the rlog (…" |
| contract-acknowledged | binary | True | None | "**Operating contract:** `v` and `δ` are **clamped to measured** under the speed-…" |
| regime-breakdown-present | binary | True | None | "| Variant | Overall | Straight | Steady | Transient | Marginal vs prev | Note |" |
| methodology-consistent | binary | True | None | "**Segment set:** first 20 Mach-E `sim.csv` files under `data/sim/segments/FORD_M…" |
| attribution-coherent | numeric | True | True | "Marginal sum V0→V4 = +0.00046; total drop V0→V4 = +0.00046 (within 15% by coinci…" |
| honest-regression-flagged | binary | True | None | "| V2 linear ST, prior Cα | 0.01606 | 0.00351 | 0.06072 | 0.08514 | +0.00238 | **…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Report explicitly names the scored channel and identifies it as measured, citing the Ford party DBC in the rlog.
- evidence:
  > `yaw_rate_meas_rads` is **measured** truth from the Ford party DBC in the rlog (IMU yaw rate).

### contract-acknowledged
- result: `True`
- reasoning: Explicit statement of which channels are clamped to measured and which is predicted/scored.
- evidence:
  > **Operating contract:** `v` and `δ` are **clamped to measured** under the speed-known contract (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Lateral-only metric: `yaw_rate_pred_rads − yaw_rate_meas_rads`.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table breaks out RMSE per regime (Straight/Steady/Transient) in addition to overall.
- evidence:
  > | Variant | Overall | Straight | Steady | Transient | Marginal vs prev | Note |

### methodology-consistent
- result: `True`
- reasoning: Fixed segment-set and regime mask declared up front, with a single shared variant table using the same metric (RMSE rad/s) and same regime columns for every variant.
- evidence:
  > **Segment set:** first 20 Mach-E `sim.csv` files under `data/sim/segments/FORD_MUSTANG_MACH_E_MK1/` (sorted), 57,979 rows total. Regime split: straight 55,076 / steady 1,901 / transient 1,002.

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Marginal sum equals total drop exactly per the agent's reconciliation, so |Σ marginals − total|/|total| = 0 < 0.15.
- evidence:
  > Marginal sum V0→V4 = +0.00046; total drop V0→V4 = +0.00046 (within 15% by coincidence — regressions and the V4 recovery nearly cancel).

### honest-regression-flagged
- result: `True`
- reasoning: Variant table flags V2, V3, V4 explicitly as regressions with physical/causal reasons (over-stiff cornering response, solver convergence failure, still worse than V1).
- evidence:
  > | V2 linear ST, prior Cα | 0.01606 | 0.00351 | 0.06072 | 0.08514 | +0.00238 | **regression overall**: prior Cα over-stiffens cornering response |
