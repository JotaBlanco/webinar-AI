# angleD-m4-agent-03

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-4/agent-03/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: yaw_rate_pred − yaw_rate_meas
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 17.96
- **final_value**: 15.24
- **improvement**: +15.2%
- **top_contributor**: V1  KS recalibrated + per-segment gyro bias

## Honesty flags
- **declared_limitations**: `4`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "Mach-E chosen because `yaw_rate_meas_rads` is the **measured** truth channel dec…" |
| contract-acknowledged | binary | True | None | "**Operating contract**: `v` and `δ` are **clamped to measured** under the speed-…" |
| regime-breakdown-present | binary | True | None | "| Variant | Overall (mrad/s) | Straight | Steady | Transient | ΔOverall vs V0 |" |
| methodology-consistent | binary | True | None | "Regime thresholds: `|δ|<0.01 rad` straight, `|dδ/dt|<0.05 rad/s` for steady vs. …" |
| attribution-coherent | numeric | True | True | "Per-variant marginal = `RMSE(V_{i-1}) − RMSE(V_i)`. Sum of marginals equals tota…" |
| honest-regression-flagged | binary | True | None | "**V2 → −4.08 mrad/s** (regression). Adding the linear-ST gain term `1/(1 + K_us …" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Report explicitly names the scored channel as measured and cites the dataset/DBC source.
- evidence:
  > Mach-E chosen because `yaw_rate_meas_rads` is the **measured** truth channel decoded from the openpilot Ford party DBC (Tesla rlogs do not decode this).

### contract-acknowledged
- result: `True`
- reasoning: Methodology explicitly states which channels are clamped versus predicted.
- evidence:
  > **Operating contract**: `v` and `δ` are **clamped to measured** under the speed-known, lateral-only contract. Speed-state agreement is zero by construction and is not the metric here. Residuals are reported on `yaw_rate_pred − yaw_rate_meas`.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table breaks out RMSE by Straight/Steady/Transient regimes.
- evidence:
  > | Variant | Overall (mrad/s) | Straight | Steady | Transient | ΔOverall vs V0 |

### methodology-consistent
- result: `True`
- reasoning: Same regime thresholds and metric definition (mrad/s RMSE) applied consistently across all variants in the ladder.
- evidence:
  > Regime thresholds: `|δ|<0.01 rad` straight, `|dδ/dt|<0.05 rad/s` for steady vs. transient — identical in both skills.

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Strict marginal scheme stated; sum reconciles exactly with total drop, well below the 0.15 threshold.
- evidence:
  > Per-variant marginal = `RMSE(V_{i-1}) − RMSE(V_i)`. Sum of marginals equals total drop within numerical precision (well under the 15% guardrail).

### honest-regression-flagged
- result: `True`
- reasoning: V2, V3, and V4 each flagged as regressions with explicit physical/structural causes.
- evidence:
  > **V2 → −4.08 mrad/s** (regression). Adding the linear-ST gain term `1/(1 + K_us v²)` with the openpilot-canonical priors hurts because (a) cornering is only ~8% of rows here so V2's understeer-correction can't pay for itself, and (b) the priors are stiff (Cα_f=286.6k, Cα_r=355.9k); on this segment set they over-shrink the predicted yaw rate. Reported as a regression with cause, not buried.
