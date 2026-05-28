# angleE-m3-agent-02

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-3/agent-02/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: RMSE of yaw-rate residual, rad/s
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.016127
- **final_value**: 0.016635
- **improvement**: Total drop V0→V3: **−0.000508 rad/s** (i.e. the ladder ends worse than it started).
- **top_contributor**: V1  KS recalib + per-seg bias

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `False`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "Truth channel: `yaw_rate_meas_rads` is the measured ground truth in each Ford `s…" |
| contract-acknowledged | binary | True | None | "Inputs `v` and `δ` are clamped to measured (`clamp_v_to_measured=True`, `clamp_d…" |
| regime-breakdown-present | binary | True | None | "| variant | overall | straight | steady   | transient | marginal drop (overall) …" |
| methodology-consistent | binary | True | None | "(Sign convention: negative = RMSE improved relative to V0; positive = regression…" |
| attribution-coherent | numeric | True | True | "Attribution scheme: strict marginal, fixed order V0→V1→V2→V3. Marginal drop = `R…"; "Total drop V0→V3: **−0.000508 rad/s** (i.e. the ladder ends worse than it starte…" |
| honest-regression-flagged | binary | True | None | "**V2 (Linear ST prior) — regression in steady & transient.** Physical cause: sma…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Report names the scored channel and identifies it as the measured ground truth from the Ford sim.csv dataset.
- evidence:
  > Truth channel: `yaw_rate_meas_rads` is the measured ground truth in each Ford `sim.csv`.

### contract-acknowledged
- result: `True`
- reasoning: Methodology explicitly states which channels are clamped to truth (v and δ) and which is predicted/scored (yaw-rate residual).
- evidence:
  > Inputs `v` and `δ` are clamped to measured (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Speed-state agreement is zero by construction and is not the metric. Only the lateral residual (RMSE of `pred − meas`) is reported.

### regime-breakdown-present
- result: `True`
- reasoning: The variant ladder table breaks RMSE out by straight/steady/transient regimes alongside overall.
- evidence:
  > | variant | overall | straight | steady   | transient | marginal drop (overall) | notes |

### methodology-consistent
- result: `True`
- reasoning: Both the variant ladder and the regime-contrast tables share the same fixed segment/regime mask and metric definition, explicitly reconciled.
- evidence:
  > (Sign convention: negative = RMSE improved relative to V0; positive = regression. Same `regime` column as the parent table, so the numbers reconcile.)

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Marginal column and total drop are both present; sum of marginals reconciles exactly (0.0% error), well below the 0.15 threshold.
- evidence:
  > Attribution scheme: strict marginal, fixed order V0→V1→V2→V3. Marginal drop = `RMSE(V_{i-1}) − RMSE(V_i)`. Sum of marginals reconciles to total drop within 0.0% (well under the 15% tolerance the skill mandates).
  > Total drop V0→V3: **−0.000508 rad/s** (i.e. the ladder ends worse than it started). Sum of marginals: −0.000508. Reconciliation error: 0.0%.

### honest-regression-flagged
- result: `True`
- reasoning: Report explicitly flags V2 and V3 as regressions and gives physical causes (small-angle linearisation, flat loss-surface region, functional-form limit).
- evidence:
  > **V2 (Linear ST prior) — regression in steady & transient.** Physical cause: small-angle linearisation + steady-state assumption. Real Mach-E cornering data violates both; `tan(δ)` (V1) actually fits better than `δ/(1+K_us v²)` here.
