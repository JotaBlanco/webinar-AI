# angleC-m3-agent-04

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-3/agent-04/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: Lateral yaw-rate RMSE
- **platform**: Mach-E (segment-bias variant) and Lightning (per-platform affine variant)
- **baseline_value**: 0.02037
- **final_value**: 0.01654
- **improvement**: 18.8% on Lightning
- **top_contributor**: V3 steering gain k=0.892

## Honesty flags
- **declared_limitations**: `4`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "**Measured truth**: Ford has `yaw_rate_meas_rads` from CAN; Tesla does not (rule…" |
| contract-acknowledged | binary | True | None | "**Clamped vs predicted**: `v_mps` and `delta_road_rad` clamped to measured (late…" |
| regime-breakdown-present | binary | True | None | "| Variant | overall | straight | steady | transient | scope |" |
| methodology-consistent | binary | True | None | "## Variant ladder (held-out interleaved every-5th-sample TEST, rule 7)" |
| attribution-coherent | numeric | True | True | "Attribution: strict marginal V0→V1→V2→V3→V4." |
| honest-regression-flagged | binary | True | None | "V3 worsens **straight** RMSE on Mach-E (0.00878 → 0.00999): k>1 amplifies near-z…"; "V4 vs V3 on Mach-E transient regressed (0.05085 → 0.05214): bias term stole vari…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Agent names the scored channel (yaw_rate_meas_rads) and explicitly identifies it as measured from CAN on Ford platforms.
- evidence:
  > **Measured truth**: Ford has `yaw_rate_meas_rads` from CAN; Tesla does not (rule 4 — Tesla excluded).

### contract-acknowledged
- result: `True`
- reasoning: Explicit clamped-vs-predicted statement is present in the Setting section.
- evidence:
  > **Clamped vs predicted**: `v_mps` and `delta_road_rad` clamped to measured (lateral-only mode); ψ̇ and a_y predicted (rule 5).

### regime-breakdown-present
- result: `True`
- reasoning: Variant tables break out RMSE per regime (straight / steady / transient) for both platforms.
- evidence:
  > | Variant | overall | straight | steady | transient | scope |

### methodology-consistent
- result: `True`
- reasoning: Both platform tables share the same regime columns (overall/straight/steady/transient) and the section header declares a single TEST split applied across all variants.
- evidence:
  > ## Variant ladder (held-out interleaved every-5th-sample TEST, rule 7)

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Marginal RMSE drops sum exactly to total drop on each platform (Lightning V0 0.02037 → V4 0.01654 total drop 0.00383; marginals 0.00031+0.00068+0.00240+0.00044=0.00383), reconciling to 0.
- evidence:
  > Attribution: strict marginal V0→V1→V2→V3→V4.

### honest-regression-flagged
- result: `True`
- reasoning: Regressions are explicitly listed with physical causes (jitter amplification; bias stealing variance from gain).
- evidence:
  > V3 worsens **straight** RMSE on Mach-E (0.00878 → 0.00999): k>1 amplifies near-zero δ jitter.
  > V4 vs V3 on Mach-E transient regressed (0.05085 → 0.05214): bias term stole variance from gain.
