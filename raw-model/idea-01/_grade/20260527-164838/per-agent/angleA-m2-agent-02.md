# angleA-m2-agent-02

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-2/agent-02/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: RMSE on `yaw_rate_pred − yaw_rate_meas`, rad/s
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.01550
- **final_value**: 0.01313
- **improvement**: 15.3% reduction
- **top_contributor**: V1_seg_bias

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `False`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "The `yaw_rate_meas_rads` and `a_lat_meas_mps2` columns are **measured truth** de…" |
| contract-acknowledged | binary | True | None | "**Speed-known contract honoured.** `v_mps` and `delta_road_rad` are **clamped** …" |
| regime-breakdown-present | binary | True | None | "| variant       | RMSE_overall | straight | steady  | transient | marginal Δ ove…" |
| methodology-consistent | binary | True | None | "**Segment set:** First 120 Mach-E segments (sorted), 348 060 samples at 50 Hz (~…" |
| attribution-coherent | numeric | True | True | "**Accounting:** sequential / chain decomposition — each row's marginal drop is t…" |
| honest-regression-flagged | binary | True | None | "**Regressed by 0.00127 rad/s overall.** Physical cause: the openpilot-shipped co…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Agent names the scored channel (yaw_rate_meas_rads) and identifies it as measured truth from rlog CAN.
- evidence:
  > The `yaw_rate_meas_rads` and `a_lat_meas_mps2` columns are **measured truth** decoded from rlog CAN, not predictions or self-consistency.

### contract-acknowledged
- result: `True`
- reasoning: Explicit clamped-vs-predicted statement in the methodology section.
- evidence:
  > **Speed-known contract honoured.** `v_mps` and `delta_road_rad` are **clamped** inputs; the KS state's own `v`/`δ` updates are overwritten each step. The **predicted** channel under test is `yaw_rate_pred_rads`

### regime-breakdown-present
- result: `True`
- reasoning: Variant table breaks RMSE out by straight / steady / transient regimes.
- evidence:
  > | variant       | RMSE_overall | straight | steady  | transient | marginal Δ overall | total drop vs V0 |

### methodology-consistent
- result: `True`
- reasoning: Explicit declaration that the same segment-set and regime mask are applied to every variant row.
- evidence:
  > **Segment set:** First 120 Mach-E segments (sorted), 348 060 samples at 50 Hz (~116 min driving). Same segment-set and same regime mask across every row.

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Sequential marginal drops (-0.00193, -0.00045, +0.00127) sum to -0.00111 = V0(0.01550) - V3(0.01440) = 0.00110; |Σ - total|/total ≈ 0, well under 0.15.
- evidence:
  > **Accounting:** sequential / chain decomposition — each row's marginal drop is the overall-RMSE reduction relative to the row above. Sum of signed marginal drops = V0_overall − V3_overall by construction.

### honest-regression-flagged
- result: `True`
- reasoning: V3 flagged as a regression with a physical cause (incorrect cornering-stiffness prior).
- evidence:
  > **Regressed by 0.00127 rad/s overall.** Physical cause: the openpilot-shipped cornering-stiffness prior is too small (under-correction inversion); on these segments the ST prior over-corrects relative to KS+alignment.
