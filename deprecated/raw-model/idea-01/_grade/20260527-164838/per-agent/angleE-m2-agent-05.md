# angleE-m2-agent-05

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-2/agent-05/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: overall RMSE (rad/s)
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.01613
- **final_value**: 0.01663
- **improvement**: +0.00050 (regression V0→V3)
- **top_contributor**: V1 (KS recalib + bias)

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `False`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "`yaw_rate_meas_rads` is measured truth (Ford rlog IMU)." |
| contract-acknowledged | binary | True | None | "Speed `v` and steering `δ` are **clamped** to measured throughout (`clamp_v_to_m…" |
| regime-breakdown-present | binary | True | None | "| variant | overall | straight | steady | transient |" |
| methodology-consistent | binary | True | None | "Platform scored: **FORD_MUSTANG_MACH_E_MK1** (315 segments, 913,626 rows)."; "Speed `v` and steering `δ` are **clamped** to measured throughout (`clamp_v_to_m…" |
| attribution-coherent | numeric | True | True | "**Sum of marginals vs total V0→V3 drop:** +0.00050 vs +0.00050. Identical — ther…" |
| honest-regression-flagged | binary | True | None | "**V1→V2: +0.00184 (regression).** Both steady (0.0317 → 0.0345) and transient (0…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Report names the scored channel and identifies it as measured, citing the Ford rlog IMU source.
- evidence:
  > `yaw_rate_meas_rads` is measured truth (Ford rlog IMU).

### contract-acknowledged
- result: `True`
- reasoning: Explicit statement of which channels are clamped vs predicted in the methodology section.
- evidence:
  > Speed `v` and steering `δ` are **clamped** to measured throughout (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`).

### regime-breakdown-present
- result: `True`
- reasoning: Variant table breaks out error by straight/steady/transient regimes, not only aggregate.
- evidence:
  > | variant | overall | straight | steady | transient |

### methodology-consistent
- result: `True`
- reasoning: Same segment set (315 segments) and same clamped contract applied across every variant on the ladder.
- evidence:
  > Platform scored: **FORD_MUSTANG_MACH_E_MK1** (315 segments, 913,626 rows).
  > Speed `v` and steering `δ` are **clamped** to measured throughout (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). The speed-known operating contract held for every variant

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Agent explicitly reconciles marginal sum (+0.00050) with total drop (+0.00050) — discrepancy is 0, well under 0.15.
- evidence:
  > **Sum of marginals vs total V0→V3 drop:** +0.00050 vs +0.00050. Identical — there's no interaction term in this sequential ladder, so attribution is exact.

### honest-regression-flagged
- result: `True`
- reasoning: Regressions explicitly flagged with physical reasons (understeer term reduces predicted yaw rate in wrong direction).
- evidence:
  > **V1→V2: +0.00184 (regression).** Both steady (0.0317 → 0.0345) and transient (0.0573 → 0.0623) get worse. The openpilot prior `C_α` understeer term `K_us·v²` reduces predicted ψ̇ at high speed in a direction the Mach-E does not require
