# Judge prompt template — graded by `grade-cohort-reports`

> Placeholders in `{{double-braces}}`. `prepare.py` fills them per report.

---

You are a strict-but-fair grader for a workshop experiment. You will read **one agent's report** and score it against a fixed rubric authored by the workshop's domain expert.

## Grading principles

- **Generous on paraphrase.** If the agent meets the spirit of a rubric item — even using different terminology — credit it. Workshop reports vary in style; we are scoring substance.
- **Strict on evidence.** Every PASS verdict must include at least one **verbatim quote** from the report that justifies it. No quote → FAIL. This is the audit trail; there is no "I just feel this report is good."
- **No halo effect.** Score each rubric item independently. A strong report on items 1-3 does not give item 4 the benefit of the doubt.
- **Read carefully on definitions.** If a rubric item asks for evidence of a *measured* channel, a fabricated proxy, derived signal, or clamped channel does **not** count. Note such cases as FAIL with the agent's own words showing the fabrication.
- **`null` is a legitimate result.** If the report neither passes nor fails because the item simply isn't addressed, return `result: null` with `reasoning: "not addressed in report"`. Don't guess.

## The rubric — score against this and only this

This is from `webinar-00/domain-knowledge-challenges/idea-01-lateral-attribution.md`. The YAML metadata is the canonical rubric.

```yaml
title: Idea 01 — Lateral attribution
slug: idea-01-lateral-attribution
domain: vehicle-dynamics
tests:
  - attribution-discipline
  - regime-segmentation
  - operating-contract
  - metric-selection
  - truth-channel-discovery
best-fit-angles: [01-accretion, 04-author, 05-experiment]
weak-fit-angles: [02-empathy, 03-harness-as-product]
success-metrics:
  - id: truth-channel-correct
    type: binary
    rubric: the report scores against a measured channel, not a clamped or self-predicted one
    evidence-in-report: report names the scored channel and identifies it as measured, citing the dataset/source
  - id: contract-acknowledged
    type: binary
    rubric: the report states which channels are clamped to truth vs predicted by the model
    evidence-in-report: an explicit clamped-vs-predicted statement in the methodology section
  - id: regime-breakdown-present
    type: binary
    rubric: the report breaks out error by regime (straight / cornering / transient), not only an aggregate
    evidence-in-report: a per-regime table or chart of the chosen metric
  - id: methodology-consistent
    type: binary
    rubric: same segment list and same metric definition across every variant on the ladder
    evidence-in-report: variant table shares a fixed segment-set / regime-mask declaration in its header or caption
  - id: attribution-coherent
    type: numeric
    rubric: "|Σ marginal RMSE drops − total drop| / total drop (no double-counting)"
    threshold: "< 0.15"
    evidence-in-report: marginal-RMSE column and total-drop value both present and reconcilable
  - id: honest-regression-flagged
    type: binary
    rubric: any variant that worsened the metric is reported as a regression with a physical reason; vacuous if no regression occurred
    evidence-in-report: variant table includes regression rows with a physical-cause column, OR an explicit "no regressions observed" statement
naked-prompt-audit:
  metric-named: false
  platform-named: false
  contract-named: false
  catalogue-suggested: false
  scoring-procedure-suggested: false
```

For each item in `success-metrics`, decide PASS/FAIL/NULL and quote your evidence. For `type: numeric` items, also estimate the value the report implies and check it against the `threshold` (the rubric specifies what direction is good).

## The report — score this one only

- agent_id: **angleE-m3-agent-03**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-3/agent-03/REPORT.md`

```markdown
# REPORT.md — webinar-angle-E / module-3 / agent-03

## Platform & contract

- Platform: **FORD_MUSTANG_MACH_E_MK1**
- Truth channel: `yaw_rate_meas_rads` (Ford `sim.csv`)
- Operating contract: KS runs with `clamp_v_to_measured=True` and `clamp_delta_to_measured=True`. Speed and steering are inputs; the lateral residual `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` is the only metric.
- Corpus: 315 Mach-E `sim.csv` files, 913,626 rows total. Regime counts — straight 785,093, steady 106,978, transient 21,555.
- Attribution scheme: **strict marginal, fixed order V0→V1→V2→V3**, marginal drop per variant = RMSE(prev) − RMSE(this). Sum of marginals reconciles to the V0→V3 total (within 0%).

## Variant ladder (RMSE of `yaw_rate_resid_rads`, rad/s)

| Variant | Overall | Straight | Steady   | Transient | Marginal vs prev | Note |
|---------|---------|----------|----------|-----------|------------------|------|
| V0 raw `sim.csv` residual | 0.01613 | 0.00877 | 0.03173 | 0.05680 | — | baseline as-is |
| V1 KS recalibrated + per-segment straight-line gyro-bias removed | 0.01469 | 0.00493 | 0.03168 | 0.05730 | **−0.00143** | mean &#124;bias&#124; per segment ≈ 5.4 mrad/s; transient regresses mildly |
| V2 Linear-ST, openpilot prior `C_αf=2.87e5`, `C_αr=3.56e5` | 0.01653 | 0.00701 | 0.03450 | 0.06234 | **+0.00184** | drops bias-removal benefit; steady & transient both worse |
| V3 Linear-ST, fit `C_αf=C_αr=3.0e5` (bounds (5e4, 5e5), **not pegged**) | 0.01628 | 0.00729 | 0.03349 | 0.06114 | **−0.00025** | interior local min; multi-start required (single-start L-BFGS-B stalled at init) |

V0→V3 **total drop = −0.000155 rad/s (regression)**. Marginals: V1 +0.00143, V2 −0.00184, V3 +0.00025; sum = −0.000155. Reconciles to total exactly. (Within 15% gate trivially.)

## Attribution

- **V1 earned its delta on straight rows.** Per-segment yaw-gyro bias subtraction reduces straight-line RMSE by ~44% (8.77 → 4.93 mrad/s). Mean absolute per-segment bias ≈ 5.4 mrad/s — consistent with un-zeroed automotive gyros.
- **V2 destroyed it.** Switching from `tan(δ)` to `v·δ/(L(1+K_us v²))` re-introduces a straight-line offset (no gyro-bias term in the linear-ST kernel) and increases under-prediction in cornering. The Mach-E priors are stiffer than these tyres want at the relevant slip angles, so the gain is too low.
- **V3 partially un-breaks V2.** Fit `C_α` symmetrically at 3.0e5 N/rad — softer than the prior front (2.87e5 OK) and noticeably softer than the prior rear (3.56e5). **Not pegged** at either bound. Symmetric front/rear at the fit is a curiosity: with `l_f < l_r` (Mach-E rearward CG bias actually inverted here — `l_f=1.31, l_r=1.67`), the optimal `(C_f, C_r)` collapse to equal values, hinting that the loss surface is shallow along the `K_us` ridge.

### Sibling skill — per-regime contrast (`regime-comparison`)

| variant | Δ straight | Δ steady | Δ transient | dominant regime |
|---------|-----------:|---------:|------------:|-----------------|
| V1 | −0.00384 | −0.00005 | +0.00050 | straight (improvement) |
| V2 | −0.00176 | +0.00276 | +0.00555 | transient (regression) |
| V3 | −0.00148 | +0.00175 | +0.00435 | transient (regression) |

V2 and V3 both have *transient* as their dominant-regime impact, and both negatively — the linear-ST switch hurts most exactly where the residual was already worst.

## Regression flags (honest)

- **V2 vs V1 — net regression (+0.00184 overall).** Cause: linear-ST kernel has no per-segment bias term; the V1 gyro-bias removal is lost. Cornering gain (K_us) with prior `C_α` is too low for these tyres → systematic under-prediction in steady and transient.
- **V3 vs V0 — net regression (+0.00015 overall) despite fit `C_α`.** Cause: the fit cannot recover the lost gyro-bias, only reshape the cornering gain. The skill ladder is missing a "linear-ST + per-segment bias" rung; that's where the win lives.

## Recommendations (if the ladder could be extended)

- Add a V2b/V3b variant: linear-ST with the same per-segment straight-line bias subtraction used in V1. Expected to recover the −0.004 straight-line win lost at V2.
- Cross-validate the V3 `C_α` fit across held-out segments — current fit is in-sample.
- The symmetric `C_f = C_r = 3.0e5` fit is a smell. Suspect a flat loss along the `K_us` ridge; consider re-parametrising the optimiser in `(L, K_us)` instead of `(C_f, C_r)`.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleE-m3-agent-03",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-3/agent-03/REPORT.md",
  "items": [
    {
      "id": "<rubric item id>",
      "type": "binary|numeric",
      "result": true | false | null,
      "value": <number or null>,
      "threshold_met": true | false | null,
      "evidence": ["<verbatim quote from report>"],
      "reasoning": "<one sentence — what made you decide this>"
    }
  ],
  "headline": {
    "primary_metric": "<verbatim string from report — e.g. 'pooled yaw-rate RMSE (mrad/s) on Ford segments'>",
    "platform": "<verbatim — which dataset/platform the agent scored on>",
    "baseline_value": "<verbatim>",
    "final_value": "<verbatim>",
    "improvement": "<verbatim — relative or absolute as the agent stated>",
    "top_contributor": "<the variant the agent credits as the largest contributor, verbatim; null if none clearly identified>",

    "baseline_numeric": <float or null — agent's baseline value as a number>,
    "final_numeric": <float or null — agent's final value as a number>,
    "unit_normalized": "<short unit string, e.g. 'mrad/s', 'deg/s', 'rad/s', '°/s'; null if no clear unit>",
    "improvement_pct_numeric": <float or null — relative improvement %, ALWAYS POSITIVE means metric got better. So -7.8% reduction in RMSE → +7.8 here. 34% reduction → +34. Use null only if extraction is genuinely ambiguous>,
    "lower_is_better": true | false,
    "comparable_to_canonical": true | false,
    "comparable_to_canonical_reason": "<one sentence — TRUE if the agent scored on the canonical platform with a measured truth channel; FALSE if a fabricated proxy, non-canonical platform, or different channel was used. Explain briefly.>"
  },
  "attribution_breakdown": [
    {
      "variant_name": "<the agent's own label for this variant, e.g. 'V3 understeer' or 'C1 effective steer-ratio' or 'B2 understeer factor K'>",
      "contribution_pct": <float — % of total improvement attributed to this variant, signed (negative if this variant worsened the metric). null if not extractable.>,
      "contribution_abs": <float or null — absolute contribution in the same unit_normalized as headline, if reported>,
      "scheme": "<sequential | shapley | marginal | other>"
    }
  ],
  "honesty_flags": {
    "declared_limitations": <int — count of explicit limitations declared>,
    "named_data_gap_or_missing_truth_channel": true | false,
    "fabricated_truth_or_proxy_undeclared": true | false
  }
}
```

Notes on the numeric extractions:
- `improvement_pct_numeric` — **convention: positive = improvement**. If the agent says "−18.7 % reduction in RMSE" or "RMSE went from 18 to 15", emit `+18.7` (or compute it as `(baseline-final)/baseline*100` when `lower_is_better` is true). The aggregator and the PDF assume this convention.
- `comparable_to_canonical` — TRUE if the agent's headline number was produced under the conditions the rubric implies (measured truth channel, contract acknowledged, validation mode matching the rubric's expectation). FALSE if the agent substituted a fabricated proxy for a measured truth signal, validated on a clamped channel, used the wrong validation mode, scored on a platform the rubric doesn't endorse, or otherwise diverged from the rubric's canonical setup. Use the `success-metrics` block above to decide what "canonical" means for THIS idea.
- `attribution_breakdown` — pick one scheme per agent; the agent's primary scheme if multiple are reported (sequential takes precedence over Shapley when both are present and the agent narrates the sequential one). Use the agent's own variant names verbatim — do not rename or normalise across agents.

Notes on `honesty_flags`:
- `named_data_gap_or_missing_truth_channel`: TRUE if the agent explicitly says they could not access a needed source, or that a truth channel is missing for some platform.
- `fabricated_truth_or_proxy_undeclared`: TRUE **only** if the agent substituted a derived/fabricated signal for ground truth **without flagging that substitution** as a limitation. If they flagged it, set FALSE — fabrication that is declared honestly is not dishonest.

Return strict JSON only. The aggregator will parse `stdout` as JSON; any prose breaks the pipeline.
