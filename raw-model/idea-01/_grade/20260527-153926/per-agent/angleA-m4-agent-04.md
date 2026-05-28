# angleA-m4-agent-04

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-4/agent-04/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: Overall RMSE (rad/s)
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.01214
- **final_value**: 0.01005
- **improvement**: 0.00210 rad/s (17.3% reduction)
- **top_contributor**: V4 — Ridge residual learner on V3, LOSO CV

## Honesty flags
- **declared_limitations**: `4`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "Lateral-truth channel is `yaw_rate_meas_rads`, the **measured** yaw rate decoded…" |
| contract-acknowledged | binary | True | None | "All Ford `sim.csv` rows were produced with `clamp_v_to_measured=True` and `clamp…" |
| regime-breakdown-present | binary | True | None | "| Variant | Overall RMSE (rad/s) | Straight | Steady | Transient | Marginal Δ (r…" |
| methodology-consistent | binary | True | None | "Same segment set and same regime mask are **held constant across every row** in …" |
| attribution-coherent | numeric | True | True | "Total drop V0 → V4: **0.00210 rad/s** (17.3% reduction). Sum of marginal drops: …" |
| honest-regression-flagged | binary | True | None | "**V2 (regression, +0.00193).** Switched to the linear single-track steady-state …" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Report explicitly names the scored channel and identifies it as a measured IMU-decoded signal.
- evidence:
  > Lateral-truth channel is `yaw_rate_meas_rads`, the **measured** yaw rate decoded from the rlog IMU (not predicted, not the KS integrator state).

### contract-acknowledged
- result: `True`
- reasoning: Methodology explicitly states which channels are clamped to measured truth and which are predicted.
- evidence:
  > All Ford `sim.csv` rows were produced with `clamp_v_to_measured=True` and `clamp_delta_to_measured=True`, so `v_mps` and `delta_road_rad` are **clamped** inputs and `yaw_rate_pred_rads` is the resulting **predicted** lateral output.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table breaks out RMSE by Straight/Steady/Transient regimes for each variant.
- evidence:
  > | Variant | Overall RMSE (rad/s) | Straight | Steady | Transient | Marginal Δ (rad/s) |

### methodology-consistent
- result: `True`
- reasoning: Report explicitly states the segment set and regime mask are fixed across all variants.
- evidence:
  > Same segment set and same regime mask are **held constant across every row** in the variant ladder.

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Marginal drops sum to the total and the report explicitly computes coherence error as 0.00, well below 0.15.
- evidence:
  > Total drop V0 → V4: **0.00210 rad/s** (17.3% reduction). Sum of marginal drops: 0.00210 rad/s. Coherence error `|Σmarg − total|/|total| = 0.00 < 0.15`.

### honest-regression-flagged
- result: `True`
- reasoning: V2 and V3 are explicitly labelled as regressions with physical causes (stiffer-than-needed prior, missing slip-angle dynamics term).
- evidence:
  > **V2 (regression, +0.00193).** Switched to the linear single-track steady-state yaw-rate gain `ψ̇ = v·δ / (L·(1 + K_us·v²))` with openpilot's prior cornering stiffnesses. **Worsened steady and transient cornering** (the regimes ST is supposed to help).
