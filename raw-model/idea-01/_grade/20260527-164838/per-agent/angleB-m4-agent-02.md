# angleB-m4-agent-02

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-4/agent-02/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: all-regime RMSE
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.01613
- **final_value**: 0.01515
- **improvement**: Total drop V0→V3 = -0.000972
- **top_contributor**: V1 + per-segment straight-line bias

## Honesty flags
- **declared_limitations**: `4`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "The channel under test is `yaw_rate_pred_rads`; truth is `yaw_rate_meas_rads`; r…"; "Tesla excluded — no IMU truth channel." |
| contract-acknowledged | binary | True | None | "**Clamped vs predicted:** `v_mps` and `delta_road_rad` are inputs (`clamp_v_to_m…" |
| regime-breakdown-present | binary | True | None | "| # | Variant | all RMSE | straight | steady | transient | Δ all | named drop |" |
| methodology-consistent | binary | True | None | "**Regime mask** (fixed): straight `|δ|<0.01`; steady `|δ|≥0.01 ∧ |δ̇|<0.05`; tra…"; "## Variant ladder (locked V0 → V3, strict marginal accounting on all-regime RMSE…" |
| attribution-coherent | numeric | True | True | "**Accounting:** strict marginal, fixed V0→V3 order, all-regime RMSE. Total drop …" |
| honest-regression-flagged | binary | True | None | "**V2 is a regression on cornering** (+8% steady, +10% transient). Openpilot's pr…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Report explicitly names the scored channel and identifies yaw_rate_meas_rads as the measured truth channel, with the Ford Mach-E dataset as source.
- evidence:
  > The channel under test is `yaw_rate_pred_rads`; truth is `yaw_rate_meas_rads`; residual `pred − meas`.
  > Tesla excluded — no IMU truth channel.

### contract-acknowledged
- result: `True`
- reasoning: Explicit clamped-vs-predicted statement is present in the methodology section.
- evidence:
  > **Clamped vs predicted:** `v_mps` and `delta_road_rad` are inputs (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). The channel under test is `yaw_rate_pred_rads`; truth is `yaw_rate_meas_rads`; residual `pred − meas`.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table breaks RMSE out by straight, steady, and transient regimes for each variant.
- evidence:
  > | # | Variant | all RMSE | straight | steady | transient | Δ all | named drop |

### methodology-consistent
- result: `True`
- reasoning: Fixed regime mask is declared and the variant ladder header states the metric (all-regime RMSE) is applied uniformly.
- evidence:
  > **Regime mask** (fixed): straight `|δ|<0.01`; steady `|δ|≥0.01 ∧ |δ̇|<0.05`; transient `|δ|≥0.01 ∧ |δ̇|≥0.05`. Counts: 785 093 / 107 055 / 21 478.
  > ## Variant ladder (locked V0 → V3, strict marginal accounting on all-regime RMSE)

### attribution-coherent
- result: `True`
- value: `0.003`, threshold_met: `True`
- reasoning: Reconciliation explicit: |sum of marginals − total drop|/|total drop| ≈ 0.003, well under 0.15 threshold.
- evidence:
  > **Accounting:** strict marginal, fixed V0→V3 order, all-regime RMSE. Total drop V0→V3 = -0.000972; sum of marginals = -0.000969; within 0.3% — well inside 15% tolerance. No double-counting.

### honest-regression-flagged
- result: `True`
- reasoning: V2 is explicitly flagged as a regression with a physical cause (openpilot prior C_α understeers the Mach-E too much).
- evidence:
  > **V2 is a regression on cornering** (+8% steady, +10% transient). Openpilot's prior C_α understeers the Mach-E *more* than KS does on these roads.
