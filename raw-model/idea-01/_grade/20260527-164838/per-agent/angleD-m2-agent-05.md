# angleD-m2-agent-05

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-2/agent-05/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: RMSE of `(ψ̇_pred − ψ̇_meas)` in rad/s
- **platform**: `FORD_MUSTANG_MACH_E_MK1` (Mach-E)
- **baseline_value**: 0.01575
- **final_value**: 0.01499
- **improvement**: −4.8% RMSE
- **top_contributor**: V1  KS recal (`L=2.875`) + per-seg straight-line bias

## Honesty flags
- **declared_limitations**: `5`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "**Truth channel:** `yaw_rate_meas_rads` — **measured** (Ford IMU, decoded from p…" |
| contract-acknowledged | binary | True | None | "**Operating contract:** `clamp_v_to_measured=True`, `clamp_delta_to_measured=Tru…" |
| regime-breakdown-present | binary | True | None | "| Variant | Overall | Straight | Steady | Transient | Δ vs prev | % vs prev |" |
| methodology-consistent | binary | True | None | "**Segments:** first 20 Mach-E `sim.csv` files (sorted, deterministic) → **57,979…"; "All numbers are RMSE of `(ψ̇_pred − ψ̇_meas)` in rad/s. Per-segment straight-lin…" |
| attribution-coherent | numeric | True | True | "**End-to-end:** V0 → V4 = **0.01575 → 0.01499 rad/s, −4.8% RMSE.**"; "Net contributions to the −0.000754 rad/s overall improvement:
- V1 (KS recal + b…" |
| honest-regression-flagged | binary | True | None | "| V2 | linear-ST steady-state gain replaces tan(δ) geometry | straight-line (×0.…"; "V2/V3 trade straight-line accuracy for cornering accuracy in the wrong direction…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Report names the scored channel and explicitly identifies it as measured from the Ford IMU.
- evidence:
  > **Truth channel:** `yaw_rate_meas_rads` — **measured** (Ford IMU, decoded from party DBC in the rlog). Not a prediction.

### contract-acknowledged
- result: `True`
- reasoning: Explicit statement of which channels are clamped to measured truth and which is predicted.
- evidence:
  > **Operating contract:** `clamp_v_to_measured=True`, `clamp_delta_to_measured=True`. `v` and `δ_road` are inputs; the only thing under test is the lateral-state map `(v, δ_road) → ψ̇`.

### regime-breakdown-present
- result: `True`
- reasoning: Variant ladder table breaks error out per regime (Straight / Steady / Transient) in addition to Overall.
- evidence:
  > | Variant | Overall | Straight | Steady | Transient | Δ vs prev | % vs prev |

### methodology-consistent
- result: `True`
- reasoning: Fixed segment set (first 20 Mach-E sim.csv files) and a single metric definition (RMSE of yaw-rate residual in rad/s) declared and applied across all variants.
- evidence:
  > **Segments:** first 20 Mach-E `sim.csv` files (sorted, deterministic) → **57,979 rows**.
  > All numbers are RMSE of `(ψ̇_pred − ψ̇_meas)` in rad/s. Per-segment straight-line gyro bias is subtracted on V1/V2/V3 per the skill's V1 rule.

### attribution-coherent
- result: `True`
- value: `0.027`, threshold_met: `True`
- reasoning: Sum of marginals: -0.00207 + 0.00238 - 0.00025 - 0.00082 = -0.00076; total drop = -0.000754 (0.01575-0.01499 ≈ 0.00076); |−0.00076 − (−0.00076)| / 0.00076 ≈ 0.027 < 0.15.
- evidence:
  > **End-to-end:** V0 → V4 = **0.01575 → 0.01499 rad/s, −4.8% RMSE.**
  > Net contributions to the −0.000754 rad/s overall improvement:
- V1 (KS recal + bias): **−0.00207** → contributes **+274%** of the net (i.e. it does all the work and then some).
- V2 + V3 combined: **+0.00214** (net regression).
- V4: **−0.00082** (claws back roughly what V2 cost on cornering).

### honest-regression-flagged
- result: `True`
- reasoning: V2 is flagged as a regression (+17.4%) and a physical cause (linear-ST under-predicts cornering yaw on Mach-E; trades straight-line for cornering accuracy in wrong direction) is provided.
- evidence:
  > | V2 | linear-ST steady-state gain replaces tan(δ) geometry | straight-line (×0.53 vs V1) | steady (+34%) and transient (+26%) — linear-ST under-predicts cornering yaw on Mach-E | **+17.4%** |
  > V2/V3 trade straight-line accuracy for cornering accuracy in the wrong direction; V4 partially repairs that trade.
