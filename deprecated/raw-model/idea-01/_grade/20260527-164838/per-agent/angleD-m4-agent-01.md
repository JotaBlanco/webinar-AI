# angleD-m4-agent-01

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-4/agent-01/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: Overall RMSE (rad/s)
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: RMSE(V0) = 0.01082
- **final_value**: RMSE(V1) = 0.00885
- **improvement**: an 18.2 % drop vs V0
- **top_contributor**: V1 — KS recalibrated + per-segment straight-line yaw-gyro de-bias

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `False`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "`yaw_rate_meas_rads` is **measured truth** decoded from the openpilot rlog IMU; …" |
| contract-acknowledged | binary | True | None | "**Contract:** speed-known, lateral-only. `v_mps` and `delta_road_rad` are **clam…" |
| regime-breakdown-present | binary | True | None | "| Variant | Overall RMSE (rad/s) | Straight | Steady cornering | Transient corne…" |
| methodology-consistent | binary | True | None | "**Segment set:** 12 Mach-E segments, 34 860 rows. Regime counts: 29 907 straight…"; "Both skills share thresholds (`|δ|<0.01`, `|dδ/dt|<0.05`) — verified 1.0000 lock…" |
| attribution-coherent | numeric | True | True | "Sum of marginals = 0.00042 rad/s = total drop V0→V4 (within 15 % — telescoping h…"; "Sum of strict-marginal drops V0→V4 = 0.00042 = total drop V0→V4 (exact telescope…" |
| honest-regression-flagged | binary | True | None | "V2 — Linear ST, prior Cα (openpilot-canonical Mach-E values) | 0.01028 | 0.00318…"; "**regression** — OOF RMSE = 0.01040 > V3, does not generalise; shipped as V3 not…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Agent explicitly names the scored channel and identifies it as a measured IMU channel from the openpilot rlog.
- evidence:
  > `yaw_rate_meas_rads` is **measured truth** decoded from the openpilot rlog IMU; not a derived channel.

### contract-acknowledged
- result: `True`
- reasoning: Explicit clamped-vs-predicted statement in the methodology header naming clamped channels and the residual under test.
- evidence:
  > **Contract:** speed-known, lateral-only. `v_mps` and `delta_road_rad` are **clamped to measured** at each KS step (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`).

### regime-breakdown-present
- result: `True`
- reasoning: Variant table provides per-regime RMSE columns (straight / steady cornering / transient cornering) for every variant.
- evidence:
  > | Variant | Overall RMSE (rad/s) | Straight | Steady cornering | Transient cornering | Marginal Δ vs prev | Verdict |

### methodology-consistent
- result: `True`
- reasoning: Fixed segment set and shared regime-mask thresholds declared up-front and verified at runtime, applied uniformly across the ladder.
- evidence:
  > **Segment set:** 12 Mach-E segments, 34 860 rows. Regime counts: 29 907 straight / 4 148 steady cornering / 805 transient cornering.
  > Both skills share thresholds (`|δ|<0.01`, `|dδ/dt|<0.05`) — verified 1.0000 lockstep agreement at runtime.

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Agent states the sum of marginal drops equals the total drop exactly (telescoping), so |Σ-total|/total ≈ 0, well below 0.15.
- evidence:
  > Sum of marginals = 0.00042 rad/s = total drop V0→V4 (within 15 % — telescoping holds, no overlap).
  > Sum of strict-marginal drops V0→V4 = 0.00042 = total drop V0→V4 (exact telescope, well within 15 % tolerance).

### honest-regression-flagged
- result: `True`
- reasoning: Variant table includes regression rows (V2, V3, V4) each labelled as regression with a physical cause column.
- evidence:
  > V2 — Linear ST, prior Cα (openpilot-canonical Mach-E values) | 0.01028 | 0.00318 | 0.02193 | 0.04144 | +0.00142 | **regression vs V1** — prior stiffness over-rotates this dataset on cornering
  > **regression** — OOF RMSE = 0.01040 > V3, does not generalise; shipped as V3 not V4 per skill rule
