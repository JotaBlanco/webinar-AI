# angleA-m2-agent-04

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-2/agent-04/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: RMSE of `yaw_rate_resid_rads = yaw_rate_pred − yaw_rate_meas` (rad/s)
- **platform**: `FORD_MUSTANG_MACH_E_MK1` (Ford Mach-E MK1, 315 segments, 913,626 samples @ 50 Hz)
- **baseline_value**: 0.01613
- **final_value**: 0.01077
- **improvement**: total drop = 33.2% overall (V0 0.01613 → V4 0.01077)
- **top_contributor**: V3_perseg_gain_fit

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "Truth channels are `yaw_rate_meas_rads` and `a_lat_meas_mps2` — **measured** (Fo…" |
| contract-acknowledged | binary | True | None | "**Clamped (inputs):** `v_mps`, `delta_road_rad` (overridden to measured each ste…"; "**Predicted (outputs):** `yaw_rate_pred_rads`, `a_y_pred_mps2`." |
| regime-breakdown-present | binary | True | None | "| Variant | RMSE all (rad/s) | Straight | Corner steady | Corner trans. | Margin…" |
| methodology-consistent | binary | True | None | "## Regime mask (same for all variants)" |
| attribution-coherent | numeric | True | True | "**Accounting:** sequential marginal decomposition along V0→V4. Sum of marginals …" |
| honest-regression-flagged | binary | True | None | "A direct ST-understeer correction **without** per-segment bias and gain (tested …" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Agent names the scored channel and explicitly identifies it as measured from Ford CAN-decoded IMU.
- evidence:
  > Truth channels are `yaw_rate_meas_rads` and `a_lat_meas_mps2` — **measured** (Ford CAN-decoded IMU/yaw), not model self-consistency.

### contract-acknowledged
- result: `True`
- reasoning: Explicit clamped-vs-predicted statement under 'Speed-known contract' section.
- evidence:
  > **Clamped (inputs):** `v_mps`, `delta_road_rad` (overridden to measured each step in `simulate_ks`).
  > **Predicted (outputs):** `yaw_rate_pred_rads`, `a_y_pred_mps2`.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table breaks RMSE by straight / corner-steady / corner-transient regimes.
- evidence:
  > | Variant | RMSE all (rad/s) | Straight | Corner steady | Corner trans. | Marginal Δ |

### methodology-consistent
- result: `True`
- reasoning: Header explicitly declares the regime mask is shared across all variants, and the table uses one fixed metric definition.
- evidence:
  > ## Regime mask (same for all variants)

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Sum of marginal drops equals total drop exactly; |0.00536 − 0.00536| / 0.00536 = 0.0, well below 0.15.
- evidence:
  > **Accounting:** sequential marginal decomposition along V0→V4. Sum of marginals = 0.00536, exactly equal to V0 − V4 = 0.00536.

### honest-regression-flagged
- result: `True`
- reasoning: A regression case is explicitly reported with quantified worsening and an attached physical cause.
- evidence:
  > A direct ST-understeer correction **without** per-segment bias and gain (tested as exploratory pre-final V3) made the metric **worse** (0.01613 → 0.02173, +35%). Physical cause: dominant residual is a **sign-asymmetric mean offset** (left turns under-predict by ~7 mrad/s; right turns near-zero), not the symmetric high-`a_y` yaw suppression `K_us` models.
