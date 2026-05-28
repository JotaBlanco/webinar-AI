# angleA-m4-agent-03

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-4/agent-03/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: Overall yaw-rate RMSE
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: V0 = 0.016127 rad/s
- **final_value**: V4 = 0.014897 rad/s
- **improvement**: 7.6% relative improvement
- **top_contributor**: V1

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `False`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "Scored channel: `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads`.…" |
| contract-acknowledged | binary | True | None | "Speed-known contract: `v` and `δ` are **clamped** to the measured values in the …" |
| regime-breakdown-present | binary | True | None | "| Variant | Description | RMSE overall | Straight | Steady | Transient | Δ vs pr…" |
| methodology-consistent | binary | True | None | "Methodology: same segment set and same regime mask **held constant across every …" |
| attribution-coherent | numeric | True | True | "**Attribution scheme:** strict marginal, fixed order V0→V1→V2→V3→V4. Total drop …" |
| honest-regression-flagged | binary | True | None | "**V2 regressed against V1** (overall +0.000819). This is the predicted Mach-E be…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Report explicitly names the scored channel and identifies the truth source as the measured rlog gyro, neither predicted nor clamped.
- evidence:
  > Scored channel: `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads`. `yaw_rate_meas_rads` is the **measured** truth channel decoded from the rlog gyro; it is not predicted and is not clamped.

### contract-acknowledged
- result: `True`
- reasoning: Methodology section explicitly states which channels are clamped to truth and which are predicted.
- evidence:
  > Speed-known contract: `v` and `δ` are **clamped** to the measured values in the KS integrator. The **predicted** quantity under test is `yaw_rate_pred_rads` (V0) and its V1–V4 re-predictions.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table breaks out RMSE per regime (straight, steady, transient) in addition to the overall aggregate.
- evidence:
  > | Variant | Description | RMSE overall | Straight | Steady | Transient | Δ vs prev |

### methodology-consistent
- result: `True`
- reasoning: Explicit declaration that the same segment set, regime mask, and metric are held constant across every variant row.
- evidence:
  > Methodology: same segment set and same regime mask **held constant across every variant row**. Regimes: `straight` (`|δ_road|<0.01`), `steady` (`|δ_road|≥0.01 ∧ |δ̇|<0.05`), `transient` (`|δ_road|≥0.01 ∧ |δ̇|≥0.05`). All RMSE values in rad/s on `yaw_rate_resid_rads`.

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Marginal column and total drop are present and reconcile exactly; coherence ratio ~0.000 is far below the 0.15 threshold.
- evidence:
  > **Attribution scheme:** strict marginal, fixed order V0→V1→V2→V3→V4. Total drop V0→V4 = 0.001230 rad/s; signed Σ of the Δ column = -0.001230; `|Σmarg − total|/total ≈ 0.000` (well under the 15% coherence threshold).

### honest-regression-flagged
- result: `True`
- reasoning: V2 regression is explicitly flagged with a physical cause (stiff prior C_α mismatches Mach-E lateral compliance).
- evidence:
  > **V2 regressed against V1** (overall +0.000819). This is the predicted Mach-E behaviour: the openpilot ST prior `C_α` values are **stiffer than this car's tyres actually behave**, so the steady-state ST gain over-corrects KS and worsens both cornering regimes... **Regression flagged with cause: stiff prior `C_α` mis-matches Mach-E lateral compliance.**
