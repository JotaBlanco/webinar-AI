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

- agent_id: **angleE-m3-agent-01**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-3/agent-01/REPORT.md`

```markdown
# REPORT.md — webinar-angle-E / module-3 / agent-01

## Platform & contract

- Platform: `FORD_MUSTANG_MACH_E_MK1`
- Truth channel: `yaw_rate_meas_rads` (Ford `sim.csv`)
- Operating contract: KS runs with `clamp_v_to_measured=True` and `clamp_delta_to_measured=True`. Speed and steering are inputs; the lateral residual `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` is the only metric.
- Dataset: 913,626 rows across 315 segments.
- Attribution scheme: strict marginal, fixed order V0 → V1 → V2 → V3.

## Variant ladder

| Variant | Description | RMSE overall (rad/s) | RMSE straight | RMSE steady | RMSE transient | Marginal Δ overall |
|---|---|---|---|---|---|---|
| V0 | As-shipped `yaw_rate_resid_rads` | 0.01612 | 0.00879 | 0.03169 | 0.05680 | — |
| V1 | KS recalibrated with canonical L, per-segment gyro-bias subtraction on straights | 0.01469 | 0.00496 | 0.03164 | 0.05730 | **−0.00143** (improvement) |
| V2 | Linear single-track, openpilot prior C_α (KS fallback v<2 m/s) | 0.01653 | 0.00703 | 0.03445 | 0.06235 | +0.00184 (**regression**) |
| V3 | Linear single-track, fit C_αf, C_αr bounded (5e4, 5e5) N/rad | 0.01664 | 0.00702 | 0.03478 | 0.06267 | +0.00011 (**regression**) |

Sum of marginals: −0.00051 = total drop V0→V3 (gap 0.00%, well inside the 15% tolerance).

V3 fit result: `C_αf = 1.500e5`, `C_αr = 1.500e5`, `pegged = False`. These are exactly the L-BFGS-B initial guesses — the optimizer made zero progress (silent non-convergence, not a pegged bound).

## Attribution

- **V1 owns the entire net improvement.** It cuts straight-line RMSE nearly in half (0.0088 → 0.0050) via per-segment yaw-gyro bias correction; recalibrated L is essentially neutral.
- **V2 is a regression in every regime.** Linear ST steady-state gain underestimates cornering yaw rate on this Mach-E across both steady and transient regimes.
- **V3 is V2.** The optimizer never moved off the (1.5e5, 1.5e5) prior, so the "fit" rung adds nothing.

### Per-regime contrast (sibling skill — `regime-comparison`)

Same regime column reused from the parent skill to avoid the documented mask-mismatch trap.

| Variant | Δ straight | Δ steady | Δ transient | Dominant regime |
|---|---|---|---|---|
| V0 | 0.000000 | 0.000000 | 0.000000 | — |
| V1 | **−0.00384** | −0.00005 | +0.00050 | straight |
| V2 | −0.00176 | +0.00276 | **+0.00555** | transient |
| V3 | −0.00177 | +0.00309 | **+0.00586** | transient |

Reading: V1's delta concentrates entirely on **straight** (gyro-bias correction). V2 and V3 sacrifice ~3× more in **transient** than they recover anywhere else — linear steady-state ST is the wrong model for transient cornering on this segment set.

## Regression flags

- **V2 vs V1, all three regimes.** Linear-ST steady-state gain `v·δ / (L·(1 + K_us·v²))` under-predicts yaw rate where transients and tyre nonlinearity dominate. Prior C_α from openpilot is plausibly too stiff (or too symmetric front/rear) for the Mach-E.
- **V3 vs V2, transient.** Fitting C_α inside L-BFGS-B with bounds (5e4, 5e5) terminated at the initial point: the steady-state model's loss surface is too flat near the prior for the optimizer to escape. The skill's pegged-bound regression check did not catch this failure mode — the real issue is silent non-convergence, not a bound saturation.

## Conclusion

Net improvement = V1's per-segment yaw-gyro bias correction on straights. Stepping to linear single-track loses more in cornering than it gains. To beat V1 we need a non-linear lateral model (tyre slip with saturation) or a transient-aware term — neither rung of this ladder provides one.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleE-m3-agent-01",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-3/agent-01/REPORT.md",
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
