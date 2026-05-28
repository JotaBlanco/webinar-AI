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

- agent_id: **angleE-m2-agent-04**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-2/agent-04/REPORT.md`

```markdown
# REPORT — lateral-fidelity workflow (workshop scaffold S2)

## Platform and contract

- Platform scored: **FORD_MUSTANG_MACH_E_MK1** (Mach-E MK1; 315 segments, 913,626 rows).
- `yaw_rate_meas_rads` is measured truth from the rlog IMU (Ford-only — no Tesla measured yaw available).
- Speed `v` and steering `δ` are clamped to measured (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Lateral residual `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` is the sole metric. No unclamping was attempted.

## Variant ladder

| variant | overall | straight | steady | transient |
|---|---:|---:|---:|---:|
| V0 (baseline KS, openpilot canonical) | 0.01613 | 0.00877 | 0.03173 | 0.05680 |
| V1 (KS recalib + per-segment yaw-gyro bias) | 0.01469 | 0.00493 | 0.03168 | 0.05730 |
| V2 (Linear ST, openpilot-prior Cα) | 0.01653 | 0.00701 | 0.03450 | 0.06234 |
| V3 (Linear ST, L-BFGS-B fit Cα) | 0.01663 | 0.00700 | 0.03482 | 0.06266 |

V3 fit: Cα_f = Cα_r = 150_000 N/rad (= x0). `pegged=False`. The optimizer never moved from initialisation.

## Attribution (overall RMSE, lower = better)

- V0→V1 marginal: **+0.00144 improvement** (8.9% relative). Almost entirely from straight regime (0.00877 → 0.00493, −44%). Steady and transient are unchanged or fractionally worse, confirming the win is gyro bias, not vehicle dynamics.
- V1→V2 marginal: **−0.00184 regression** (every regime worsens). The understeer-corrected ST `psi = v·δ / (L·(1 + K_us·v²))` returns smaller yaw than KS, and the bias correction from V1 is not carried forward by design.
- V2→V3 marginal: **−0.00010 regression** (essentially identical to V2). L-BFGS-B stalled at the init Cα; the loss is flat at x0 under the current clamps, so "fit Cα" is a misnomer here.
- Sum of marginals (−0.00050) equals total V0→V3 drop (−0.00050). Variants are not compounded — V2/V3 are computed from raw KS form, not from V1 — so the equality is bookkeeping, not a coincidence.

## Regressions and physical reasons

- V2 and V3 both regress vs V0 in **every** regime (overall, straight, steady, transient).
- Physical reading: openpilot's Mach-E Cα (286,551 / 355,912 N/rad) plus 2,336 kg mass yield a small understeer gradient `K_us ≈ m·(l_r·C_r − l_f·C_f)/(L²·C_f·C_r)` that shaves a few percent off the KS-predicted yaw. KS already over-predicts straight-line yaw (that's what the V1 bias correction shows), so multiplying by `1/(1+K_us·v²)` makes it slightly smaller — but the bigger problem, the un-removed straight-line gyro bias, dominates. ST without bias removal is worse than KS with bias removal.
- V3 not pegged but unmoved — the loss surface around x0 is flat enough that L-BFGS-B converges immediately. With most rows being straight (785,093 of 913,626 ≈ 86%), the yaw signal that Cα can influence is tiny relative to the bias-dominated residual.

## Notes — deviations and absences

- **Tool fix recorded.** `tools/step4_run_st_upgrade.py` accessed `PARAM_BY_PLATFORM[platform]` with dict subscripting (`P["L"]`), but the parameters module returns frozen dataclasses (`MachEST(...)`). Added a small `_AttrDictView` adapter inside the script so `P["L"]` returns `getattr(obj, "L")`. No physics or numerics changed. Recorded as workshop signal per AGENTS.md's "do not deviate, record deviation" clause.
- **Ladder caps at V3.** Per AGENTS.md, no V4 residual learner is permitted in this workflow tier, even though V1's bias-removal pattern strongly suggests a per-segment residual model would beat all three ST variants. Painful absence: cannot port V1's bias correction into V2/V3 to test whether ST helps once bias is gone.
- **Single platform.** No room to switch to F-150 Lightning to cross-check whether ST's regression is Mach-E-specific (mass and rear-bias) or general.
- **V3 honesty.** With pegged=False but Cα at x0, V3 is functionally a tied repeat of V2 at the init point, not an independent fit. Treat it as such.
- **Headline recommendation if forced to pick one:** ship V1. Reject V2/V3 on this dataset.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleE-m2-agent-04",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-2/agent-04/REPORT.md",
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
