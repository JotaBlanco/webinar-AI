# angleD-m3-agent-04

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-3/agent-04/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: Overall RMSE
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.01214
- **final_value**: 0.01005
- **improvement**: Net honest gain over V0 is 0.00210 rad/s (~17%)
- **top_contributor**: V4  Ridge residual learner on V3 (LOO out-of-fold)

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `False`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "`yaw_rate_meas_rads` is the **measured** truth channel from the rlog (Ford party…" |
| contract-acknowledged | binary | True | None | "Operating contract: `v` and `δ` are **clamped to measured** every step (speed-kn…" |
| regime-breakdown-present | binary | True | None | "| Variant | Overall RMSE | Straight | Steady | Transient | Δ vs prev | Verdict |" |
| methodology-consistent | binary | True | None | "Segment set: first 60 Mach-E `sim.csv` files under `data/sim/segments/FORD_MUSTA…"; "Residual under test: `yaw_rate_pred_rads − yaw_rate_meas_rads`, all in rad/s." |
| attribution-coherent | numeric | True | True | "Accounting: **strict marginal**, fixed order V0 → V1 → V2 → V3 → V4. Δ = RMSE(pr…" |
| honest-regression-flagged | binary | True | None | "| V2  Linear ST with prior C_α                                 | 0.01248 | 0.003…"; "| V3  Linear ST with fit C_α (Cf=150 000, Cr=150 000 N/rad)    | 0.01260 | 0.003…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Report explicitly names the scored channel as measured and cites the rlog/Ford DBC source.
- evidence:
  > `yaw_rate_meas_rads` is the **measured** truth channel from the rlog (Ford party DBC).

### contract-acknowledged
- result: `True`
- reasoning: Explicit clamped-vs-predicted statement: v and δ clamped, yaw_rate predicted.
- evidence:
  > Operating contract: `v` and `δ` are **clamped to measured** every step (speed-known, lateral-only).

### regime-breakdown-present
- result: `True`
- reasoning: Variant table breaks out RMSE across Straight, Steady, and Transient regimes.
- evidence:
  > | Variant | Overall RMSE | Straight | Steady | Transient | Δ vs prev | Verdict |

### methodology-consistent
- result: `True`
- reasoning: Fixed segment set and single residual/metric definition declared in the header for all variants.
- evidence:
  > Segment set: first 60 Mach-E `sim.csv` files under `data/sim/segments/FORD_MUSTANG_MACH_E_MK1/`.
  > Residual under test: `yaw_rate_pred_rads − yaw_rate_meas_rads`, all in rad/s.

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Marginals (−0.00159 + 0.00193 + 0.00012 − 0.00255 = −0.00209) reconcile with total drop (0.01214 − 0.01005 = 0.00209); ratio ≈1.000×, well within <0.15.
- evidence:
  > Accounting: **strict marginal**, fixed order V0 → V1 → V2 → V3 → V4. Δ = RMSE(prev) − RMSE(curr). Sum of marginals = total drop (1.000×, within 15% tolerance).

### honest-regression-flagged
- result: `True`
- reasoning: V2 and V3 explicitly labelled regressions with physical-cause explanations.
- evidence:
  > | V2  Linear ST with prior C_α                                 | 0.01248 | 0.00335 | 0.03424 | 0.06362 | +0.00193 | **regression** — ST prior C_α too stiff for these tyres; transient and steady both worsen |
  > | V3  Linear ST with fit C_α (Cf=150 000, Cr=150 000 N/rad)    | 0.01260 | 0.00343 | 0.03458 | 0.06398 | +0.00012 | **regression** — optimizer stalled at x0; loss non-convex due to K_us pole at l_r·C_αr ≈ l_f·C_αf. Not pegged at upper bound, so v0.5 pegged-check did not flag |
