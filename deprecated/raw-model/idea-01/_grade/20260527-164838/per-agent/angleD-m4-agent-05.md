# angleD-m4-agent-05

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-4/agent-05/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: RMSE in rad/s; lower is better
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.01545
- **final_value**: 0.00911
- **improvement**: Marginals sum to 0.006241; total drop is 0.006241
- **top_contributor**: V1 KS recal `(v/L) tan δ` + per-segment yaw-gyro bias on straights

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `False`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "The truth channel `yaw_rate_meas_rads` is **measured** (Ford party DBC, IMU-deco…" |
| contract-acknowledged | binary | True | None | "**Contract.** Speed-known, lateral-only. `v` (`v_mps`) and `δ` (`delta_road_rad`…" |
| regime-breakdown-present | binary | True | None | "| Variant | Description | Overall | Straight | Steady-corner | Transient-corner …" |
| methodology-consistent | binary | True | None | "Both skills share regime thresholds (`|δ|<0.01 rad` straight; `|dδ/dt|<0.05 rad/…"; "Strict marginal, fixed order V0→V1→V2→V3→V4. Each marginal drop is `RMSE(V_{i-1}…" |
| attribution-coherent | numeric | True | True | "Marginals sum to 0.006241; total drop is 0.006241 — well inside the 15% sanity b…" |
| honest-regression-flagged | binary | True | None | "**V3 regression, with a physical reason.** `fit_c_alpha` returned `Cαf = Cαr = 1…"; "Cause: with 22,155 of 23,190 rows being straight-line (where the linear-ST gain …" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Report explicitly names the scored channel and identifies it as measured, citing the source.
- evidence:
  > The truth channel `yaw_rate_meas_rads` is **measured** (Ford party DBC, IMU-decoded), not a model output.

### contract-acknowledged
- result: `True`
- reasoning: Methodology explicitly states which channels are clamped to truth vs predicted.
- evidence:
  > **Contract.** Speed-known, lateral-only. `v` (`v_mps`) and `δ` (`delta_road_rad`) are **clamped** to measured each step (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Speed-state agreement is zero by construction and not a metric.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table breaks out RMSE per regime (straight, steady-corner, transient-corner) in addition to overall.
- evidence:
  > | Variant | Description | Overall | Straight | Steady-corner | Transient-corner | Marginal (overall) |

### methodology-consistent
- result: `True`
- reasoning: Same regime thresholds and same marginal RMSE definition applied across all variants in the ladder.
- evidence:
  > Both skills share regime thresholds (`|δ|<0.01 rad` straight; `|dδ/dt|<0.05 rad/s` splits steady/transient).
  > Strict marginal, fixed order V0→V1→V2→V3→V4. Each marginal drop is `RMSE(V_{i-1}) − RMSE(V_i)` on the overall residual.

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Marginal sum equals total drop exactly; |Σ − total|/total = 0 << 0.15.
- evidence:
  > Marginals sum to 0.006241; total drop is 0.006241 — well inside the 15% sanity band.

### honest-regression-flagged
- result: `True`
- reasoning: V3 regression flagged with explicit physical reason (degenerate fit on straight-dominated data); V4 also flagged as noise/no-op.
- evidence:
  > **V3 regression, with a physical reason.** `fit_c_alpha` returned `Cαf = Cαr = 150,000 N/rad` — **exactly the L-BFGS-B initial guess (1.5e5, 1.5e5)**.
  > Cause: with 22,155 of 23,190 rows being straight-line (where the linear-ST gain is `v·δ/L` independent of Cα), the loss surface in the cornering window doesn't dominate. The "fit" is degenerate.
