# angleB-m3-agent-03

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-3/agent-03/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: RMSE of `ψ̇_pred − ψ̇_meas` in rad/s
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.01550
- **final_value**: 0.01251
- **improvement**: -0.00299
- **top_contributor**: V4 — V3 + Ridge residual LOSO on [v, |a_y|, |δ|, sign(δ̇)]

## Honesty flags
- **declared_limitations**: `5`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "Truth = `yaw_rate_meas_rads`. Tesla excluded (no IMU truth)." |
| contract-acknowledged | binary | True | None | "**Operating contract:** speed-known, lateral-only. `v` and `δ` clamped to measur…" |
| regime-breakdown-present | binary | True | None | "| Variant | all | straight | steady | transient | Δ vs prev (all) |" |
| methodology-consistent | binary | True | None | "**Regime mask:** straight (`|δ|<0.01`) 300 928, steady 39 728, transient 7 404." |
| attribution-coherent | numeric | True | True | "**Marginal-drop accounting** (greedy / sequential, one DoF per rung). Sum = -0.0…" |
| honest-regression-flagged | binary | True | None | "**V2 is a regression on `all`** (+0.00141). Linear ST with the openpilot prior `…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Report names the scored channel as the measured yaw rate and excludes platforms without measured truth.
- evidence:
  > Truth = `yaw_rate_meas_rads`. Tesla excluded (no IMU truth).

### contract-acknowledged
- result: `True`
- reasoning: Explicit clamped-vs-predicted statement appears in the methodology header.
- evidence:
  > **Operating contract:** speed-known, lateral-only. `v` and `δ` clamped to measured. Truth = `yaw_rate_meas_rads`.

### regime-breakdown-present
- result: `True`
- reasoning: Variant ladder table breaks RMSE out by straight / steady / transient regimes.
- evidence:
  > | Variant | all | straight | steady | transient | Δ vs prev (all) |

### methodology-consistent
- result: `True`
- reasoning: A fixed regime mask is declared in the header and the same columns/metric apply across every variant row.
- evidence:
  > **Regime mask:** straight (`|δ|<0.01`) 300 928, steady 39 728, transient 7 404.

### attribution-coherent
- result: `True`
- value: `0.003`, threshold_met: `True`
- reasoning: Marginal drops and the total drop are both present and reconcile to ~0.3%, comfortably under 0.15.
- evidence:
  > **Marginal-drop accounting** (greedy / sequential, one DoF per rung). Sum = -0.00298; V0→V4 = -0.00299. Closes to 0.3% — well inside the 15% bound.

### honest-regression-flagged
- result: `True`
- reasoning: V2 is explicitly flagged as a regression with a physical cause (prior C_α over-steering at high |a_y|).
- evidence:
  > **V2 is a regression on `all`** (+0.00141). Linear ST with the openpilot prior `C_α` over-steers vs measured at the high-`|a_y|` end.
