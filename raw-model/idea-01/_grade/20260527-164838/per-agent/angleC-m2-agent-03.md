# angleC-m2-agent-03

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-2/agent-03/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: lateral-yaw-rate ladder RMSE
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.924 deg/s (V0)
- **final_value**: 0.879 deg/s (V3)
- **improvement**: 4.9% global cut
- **top_contributor**: V3 + steering-gain k=1.0848 (per-platform LS, cornering-train)

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "Platform: **FORD_MUSTANG_MACH_E_MK1** (`yaw_rate_meas_rads` is measured truth, I…" |
| contract-acknowledged | binary | True | None | "`v`, `δ` clamped to measured, only lateral states predicted per rule 5" |
| regime-breakdown-present | binary | True | None | "| Variant | all | straight | steady | transient |" |
| methodology-consistent | binary | True | None | "All variants share segment set and regime masks." |
| attribution-coherent | numeric | True | True | "Marginal Δ on RMSE_all (deg/s, % of V0):
- V1 bias: -0.002 (-0.2%) — negligible
…"; "Total improvement V0→V3: **0.046 deg/s = 4.9% of baseline**" |
| honest-regression-flagged | binary | True | None | "**V3 regresses on the straight regime** (0.468 → 0.505 deg/s, +0.037). Physical …" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Agent explicitly names the scored channel as measured (IMU-decoded yaw_rate_meas_rads) on the canonical Ford platform.
- evidence:
  > Platform: **FORD_MUSTANG_MACH_E_MK1** (`yaw_rate_meas_rads` is measured truth, IMU-decoded; `v`, `δ` clamped to measured, only lateral states predicted per rule 5)

### contract-acknowledged
- result: `True`
- reasoning: Explicit clamped-vs-predicted statement is present in the methodology line.
- evidence:
  > `v`, `δ` clamped to measured, only lateral states predicted per rule 5

### regime-breakdown-present
- result: `True`
- reasoning: Variant table breaks RMSE down by straight / steady / transient regimes, not only aggregate.
- evidence:
  > | Variant | all | straight | steady | transient |

### methodology-consistent
- result: `True`
- reasoning: Agent explicitly declares the same segment set and regime masks across all ladder variants.
- evidence:
  > All variants share segment set and regime masks.

### attribution-coherent
- result: `True`
- value: `0.087`, threshold_met: `True`
- reasoning: Marginal drops sum to ~0.050 vs total 0.046; |0.050-0.046|/0.046 ≈ 0.087, well below 0.15 threshold.
- evidence:
  > Marginal Δ on RMSE_all (deg/s, % of V0):
- V1 bias: -0.002 (-0.2%) — negligible
- V2 lag: +0.015 (+1.6%)
- V3 gain: +0.033 (+3.5%)
  > Total improvement V0→V3: **0.046 deg/s = 4.9% of baseline**

### honest-regression-flagged
- result: `True`
- reasoning: Agent explicitly flags V3 regression on straight regime with a physical cause.
- evidence:
  > **V3 regresses on the straight regime** (0.468 → 0.505 deg/s, +0.037). Physical cause: scaling pred by k=1.085 also amplifies the integrator's small straight-line drift, where there is no real signal to gain-match against.
