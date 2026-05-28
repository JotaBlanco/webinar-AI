# angleA-m3-agent-04

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-3/agent-04/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: RMSE on `yaw_rate_resid_rads`, rad/s
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.012144
- **final_value**: 0.010045
- **improvement**: 0.002099 rad/s (17.3% relative)
- **top_contributor**: V4 Ridge residual learner on V3 (LOO CV)

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "The `yaw_rate_meas_rads` column is the **measured** truth channel from the rlog …" |
| contract-acknowledged | binary | True | None | "**Speed-known contract**: `v_mps` and `delta_road_rad` are **clamped** at every …" |
| regime-breakdown-present | binary | True | None | "| Variant | Overall | Straight | Steady cornering | Transient cornering | Margin…" |
| methodology-consistent | binary | True | None | "**Segments used**: 60 Mach-E `sim.csv` files (first 60 lexicographic), 173 940 r…" |
| attribution-coherent | numeric | True | True | "Total drop V0→V4 = **0.002099 rad/s (17.3% relative)**. Sum of marginals = 0.002…" |
| honest-regression-flagged | binary | True | None | "**V2 regression** vs V1 on every cornering regime. Openpilot's Mach-E prior `C_α…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Agent explicitly names the measured channel and cites the rlog gyro as its source.
- evidence:
  > The `yaw_rate_meas_rads` column is the **measured** truth channel from the rlog gyro — not a prediction, not a clamped state, not self-consistency.

### contract-acknowledged
- result: `True`
- reasoning: Methodology setup explicitly lists clamped vs predicted channels.
- evidence:
  > **Speed-known contract**: `v_mps` and `delta_road_rad` are **clamped** at every integrator step. The integrator's own speed/steer updates are discarded. The only **predicted** channels are `yaw_rate_pred_rads` and `a_y_pred_mps2`.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table breaks RMSE out by straight, steady cornering, and transient cornering regimes.
- evidence:
  > | Variant | Overall | Straight | Steady cornering | Transient cornering | Marginal Δ overall |

### methodology-consistent
- result: `True`
- reasoning: Setup explicitly declares one fixed segment set and one regime mask used across all variants.
- evidence:
  > **Segments used**: 60 Mach-E `sim.csv` files (first 60 lexicographic), 173 940 rows at 50 Hz. Same segment set, same regime mask, every row.

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Marginal sum equals total drop exactly; |Σ-total|/total = 0, well under 0.15.
- evidence:
  > Total drop V0→V4 = **0.002099 rad/s (17.3% relative)**. Sum of marginals = 0.002099 (exact).

### honest-regression-flagged
- result: `True`
- reasoning: Variants V2 and V3 are flagged as regressions with physical causes (over-stiff prior C_α, wrong DoF).
- evidence:
  > **V2 regression** vs V1 on every cornering regime. Openpilot's Mach-E prior `C_α` is too stiff for these tyres on these roads, so ST over-damps yaw rate.
