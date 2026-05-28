# angleE-m4-agent-01

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-4/agent-01/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: yaw_rate_resid_rads
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.01613
- **final_value**: 0.01469
- **improvement**: -0.00143 rad/s (-8.9%)
- **top_contributor**: V1 — KS recalib + per-segment straight-line bias

## Honesty flags
- **declared_limitations**: `4`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "`yaw_rate_meas_rads` is the measured truth channel (present on both Ford platfor…"; "`yaw_rate_resid_rads = pred − meas` is the only metric." |
| contract-acknowledged | binary | True | None | "KS runs with `clamp_v_to_measured=True`, `clamp_delta_to_measured=True`. Speed-s…" |
| regime-breakdown-present | binary | True | None | "| variant | overall | straight | steady | transient | marginal Δ overall | notes…" |
| methodology-consistent | binary | True | None | "## 2. Variant ladder (per-regime RMSE, rad/s)"; "Scheme: strict marginal, fixed order V0→V1→V2→V3. Marginal_i = RMSE(V_{i-1}) − R…" |
| attribution-coherent | numeric | True | True | "Marginal drops: V1 +0.00143, V2 −0.00184, V3 −0.00011. Sum = −0.00051. Total V0−…" |
| honest-regression-flagged | binary | True | None | "**V2 vs V1, all regimes.** Linear-ST with openpilot prior C_α (286,551 / 355,912…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Agent explicitly names yaw_rate_meas_rads as the measured truth channel and uses the residual against it as the scored metric.
- evidence:
  > `yaw_rate_meas_rads` is the measured truth channel (present on both Ford platforms, absent on Tesla).
  > `yaw_rate_resid_rads = pred − meas` is the only metric.

### contract-acknowledged
- result: `True`
- reasoning: Methodology section explicitly states which channels are clamped (v, delta) versus predicted (yaw_rate).
- evidence:
  > KS runs with `clamp_v_to_measured=True`, `clamp_delta_to_measured=True`. Speed-state agreement is zero by construction and is not the metric. `v` and `δ_road` are inputs; `yaw_rate_resid_rads = pred − meas` is the only metric.

### regime-breakdown-present
- result: `True`
- reasoning: Variant ladder table breaks RMSE out by straight/steady/transient regimes, not just an aggregate.
- evidence:
  > | variant | overall | straight | steady | transient | marginal Δ overall | notes |

### methodology-consistent
- result: `True`
- reasoning: Same regime set (straight/steady/transient) and same RMSE metric applied across every variant on the ladder.
- evidence:
  > ## 2. Variant ladder (per-regime RMSE, rad/s)
  > Scheme: strict marginal, fixed order V0→V1→V2→V3. Marginal_i = RMSE(V_{i-1}) − RMSE(V_i).

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Marginal drops sum to exactly the total drop; mismatch is 0.0%, well under the 0.15 threshold.
- evidence:
  > Marginal drops: V1 +0.00143, V2 −0.00184, V3 −0.00011. Sum = −0.00051. Total V0−V3 = −0.00051. **Mismatch 0.0%** (trivially within 15%; the check is by construction for overall RMSE).

### honest-regression-flagged
- result: `True`
- reasoning: V2 and V3 regressions are explicitly flagged in a dedicated Regression flags section with physical causes (generic prior, linearisation dropping nonlinear high-δ, missing lag).
- evidence:
  > **V2 vs V1, all regimes.** Linear-ST with openpilot prior C_α (286,551 / 355,912 N/rad) under-yaws relative to measured at the Mach-E's steering levels. Physical reason: the prior is generic, and tan(δ) → δ approximation drops nonlinear high-δ contribution that KS retains; on transients the linear model also misses lag.
