# angleC-m4-agent-05

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-4/agent-05/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: ψ̇ residual recomputed as `pred − meas`
- **platform**: FORD_MUSTANG_MACH_E_MK1 (315 segments / 913 626 samples), FORD_F_150_LIGHTNING_MK1 (230 / 667 141)
- **baseline_value**: Mach-E V0 0.01613; F-150 V0 0.02037
- **final_value**: Mach-E V4 0.01323; F-150 V4 0.01488
- **improvement**: Mach-E 0.01613→0.01323; F-150 0.02037→0.01488
- **top_contributor**: V4 per-seg bias (cal)

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "Truth = `yaw_rate_meas_rads`, `a_lat_meas_mps2` (Ford only). Operating contract:…" |
| contract-acknowledged | binary | True | None | "Operating contract: KS lateral-only, `v` and `δ` clamped, only ψ, ψ̇, a_y, x, y …" |
| regime-breakdown-present | binary | True | None | "| Variant | DOF | Overall | Straight | Steady | Transient | Marg Δ |" |
| methodology-consistent | binary | True | None | "## Variants (interleaved split, additive, locked order, per-platform fit)" |
| attribution-coherent | numeric | True | True | "Attribution coherence = 0.0000 on both." |
| honest-regression-flagged | binary | True | None | "`*` Regression: Mach-E V2 raises straight RMSE 0.00878→0.00979 — gain >1 amplifi…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Report names the measured truth channel (yaw_rate_meas_rads) explicitly and scores the predicted ψ̇ against it.
- evidence:
  > Truth = `yaw_rate_meas_rads`, `a_lat_meas_mps2` (Ford only). Operating contract: KS lateral-only, `v` and `δ` clamped, only ψ, ψ̇, a_y, x, y predicted. Score column: ψ̇ residual recomputed as `pred − meas`.

### contract-acknowledged
- result: `True`
- reasoning: Explicit clamped-vs-predicted statement is provided in the methodology header.
- evidence:
  > Operating contract: KS lateral-only, `v` and `δ` clamped, only ψ, ψ̇, a_y, x, y predicted.

### regime-breakdown-present
- result: `True`
- reasoning: Variant tables include per-regime columns (Straight / Steady / Transient) alongside Overall for both platforms.
- evidence:
  > | Variant | DOF | Overall | Straight | Steady | Transient | Marg Δ |

### methodology-consistent
- result: `True`
- reasoning: Both variant tables share the identical segment list (Straight/Steady/Transient) and an explicit fixed methodology header declared once for all variants.
- evidence:
  > ## Variants (interleaved split, additive, locked order, per-platform fit)

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Agent reports coherence of 0.0000 on both platforms, well under the 0.15 threshold; marginal column and totals are both present.
- evidence:
  > Attribution coherence = 0.0000 on both.

### honest-regression-flagged
- result: `True`
- reasoning: Regression on Mach-E V2 Straight is flagged with a physical cause (gain >1 amplifies near-zero straight noise).
- evidence:
  > `*` Regression: Mach-E V2 raises straight RMSE 0.00878→0.00979 — gain >1 amplifies near-zero straight noise; net overall still a win; kept in ladder per `ablation-study` discipline.
