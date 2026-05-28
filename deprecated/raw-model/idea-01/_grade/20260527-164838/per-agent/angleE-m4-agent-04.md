# angleE-m4-agent-04

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-4/agent-04/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: RMSE(yaw_rate_resid_rads)
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.016127
- **final_value**: 0.016635
- **improvement**: Total drop V0 → V3: **−0.00051 rad/s** (V3 is worse than V0).
- **top_contributor**: V1 — KS, canonical `L`, per-segment straight-line bias removed

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `False`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "Truth: `yaw_rate_meas_rads` (measured). Inputs `v`/`δ` are clamped to measured p…" |
| contract-acknowledged | binary | True | None | "Truth: `yaw_rate_meas_rads` (measured). Inputs `v`/`δ` are clamped to measured p…" |
| regime-breakdown-present | binary | True | None | "| variant | overall RMSE | straight | steady | transient | marginal vs prior |" |
| methodology-consistent | binary | True | None | "Per-regime regime mask uses the **skill's `δ`-based mask** (`|δ_road| < 0.01` st…" |
| attribution-coherent | numeric | True | True | "Marginal-sum accounting reconciles to 1.000× total drop (exact)." |
| honest-regression-flagged | binary | True | None | "**V2 steady: +8.7%**, **V2 transient: +9.8%** — exceed the 5% threshold. Cause: …" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Report explicitly names the scored channel and identifies it as measured.
- evidence:
  > Truth: `yaw_rate_meas_rads` (measured). Inputs `v`/`δ` are clamped to measured per the operating contract.

### contract-acknowledged
- result: `True`
- reasoning: Methodology explicitly states which channels are clamped vs predicted.
- evidence:
  > Truth: `yaw_rate_meas_rads` (measured). Inputs `v`/`δ` are clamped to measured per the operating contract. Speed-state agreement is zero by construction and is **not** the metric.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table breaks RMSE out by straight/steady/transient regimes.
- evidence:
  > | variant | overall RMSE | straight | steady | transient | marginal vs prior |

### methodology-consistent
- result: `True`
- reasoning: Fixed regime mask and RMSE metric declared once and applied across all variants in the table.
- evidence:
  > Per-regime regime mask uses the **skill's `δ`-based mask** (`|δ_road| < 0.01` straight, `|δ| ≥ 0.01 & |δ̇| < 0.05` steady, else transient).

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Marginal contributions reconcile exactly to total drop; |sum − total|/total = 0 < 0.15.
- evidence:
  > Marginal-sum accounting reconciles to 1.000× total drop (exact).

### honest-regression-flagged
- result: `True`
- reasoning: Regression flags section explicitly identifies regressions with physical-cause explanations.
- evidence:
  > **V2 steady: +8.7%**, **V2 transient: +9.8%** — exceed the 5% threshold. Cause: openpilot ST prior on Mach-E yields `K_us > 0` (understeering); but the as-shipped baseline already absorbs much of that gain implicitly through `tan(δ)` saturation at the speeds in this dataset
