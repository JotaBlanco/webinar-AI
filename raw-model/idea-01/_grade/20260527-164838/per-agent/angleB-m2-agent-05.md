# angleB-m2-agent-05

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-2/agent-05/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: RMSE of `yaw_rate_resid_rads` (rad/s)
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.01161
- **final_value**: 0.00714
- **improvement**: Total V0 → V3 drop = 0.00447 rad/s (38% of V0)
- **top_contributor**: V1 (+ per-segment yaw-rate bias removal)

## Honesty flags
- **declared_limitations**: `2`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "**Truth column:** `yaw_rate_meas_rads` — measured by the Ford chassis IMU, decod…" |
| contract-acknowledged | binary | True | None | "**Clamped (inputs):** `v_mps`, `delta_road_rad` (per `clamp_v_to_measured=True, …"; "**Predicted (under test):** `yaw_rate_pred_rads = (v/L)·tan(δ)`. Residual = pred…" |
| regime-breakdown-present | binary | True | None | "| Variant | Description | Overall | Straight | Steady cornering | Transient corn…" |
| methodology-consistent | binary | True | None | "**Regime mask** (shared across all variants): `v > 5 m/s`; straight `|δ| < 0.01 …" |
| attribution-coherent | numeric | True | True | "**Total V0 → V3 drop = 0.00447 rad/s (38% of V0).** Sum of marginals = 0.00447 (…" |
| honest-regression-flagged | binary | True | None | "V1 slightly worsens the transient regime (0.0836 → 0.0842, +0.7%). Cause: bias f…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Report names the scored channel and identifies it as a measured IMU signal with dataset/source.
- evidence:
  > **Truth column:** `yaw_rate_meas_rads` — measured by the Ford chassis IMU, decoded via `opendbc/ford_lincoln_base_pt`. Not predicted, not self-consistency.

### contract-acknowledged
- result: `True`
- reasoning: Explicit clamped vs predicted statement in methodology section.
- evidence:
  > **Clamped (inputs):** `v_mps`, `delta_road_rad` (per `clamp_v_to_measured=True, clamp_delta_to_measured=True`).
  > **Predicted (under test):** `yaw_rate_pred_rads = (v/L)·tan(δ)`. Residual = pred − meas.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table includes per-regime RMSE columns for straight, steady cornering, and transient cornering.
- evidence:
  > | Variant | Description | Overall | Straight | Steady cornering | Transient cornering | Marginal drop (vs prev) |

### methodology-consistent
- result: `True`
- reasoning: Regime mask is explicitly declared as shared across all variants with a single fixed metric (RMSE of yaw_rate_resid_rads).
- evidence:
  > **Regime mask** (shared across all variants): `v > 5 m/s`; straight `|δ| < 0.01 rad`; transient `|d(yaw_meas)/dt| > 0.5 rad/s²` on cornering; steady = remainder of cornering.

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Marginal drops sum exactly to total drop (0.00270+0.00109+0.00068=0.00447); |Σmarginal − total|/total = 0, well below 0.15.
- evidence:
  > **Total V0 → V3 drop = 0.00447 rad/s (38% of V0).** Sum of marginals = 0.00447 (perfect closure, well inside the 15% tolerance).

### honest-regression-flagged
- result: `True`
- reasoning: Regression in the transient regime is explicitly called out with a physical cause.
- evidence:
  > V1 slightly worsens the transient regime (0.0836 → 0.0842, +0.7%). Cause: bias fit on straight samples nudges genuine signed yaw-rate energy in the wrong direction in transients.
