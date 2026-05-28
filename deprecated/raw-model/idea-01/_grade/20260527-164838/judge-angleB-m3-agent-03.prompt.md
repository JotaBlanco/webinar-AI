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

- agent_id: **angleB-m3-agent-03**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-3/agent-03/REPORT.md`

```markdown
# Module-3 / agent-03 (angle-B) — Lateral Fidelity, Mach-E MK1

**Platform:** `FORD_MUSTANG_MACH_E_MK1` (315 segments available; 120 used; 348 060 samples at 50 Hz).
**Operating contract:** speed-known, lateral-only. `v` and `δ` clamped to measured. Truth = `yaw_rate_meas_rads`. Tesla excluded (no IMU truth).
**Sign sanity:** `corr(δ_road, ψ̇_meas)` on cornering = **+0.752** — convention OK.
**Regime mask:** straight (`|δ|<0.01`) 300 928, steady 39 728, transient 7 404.

## Variant ladder (RMSE of `ψ̇_pred − ψ̇_meas` in rad/s)

| Variant | all | straight | steady | transient | Δ vs prev (all) |
|---|---:|---:|---:|---:|---:|
| V0 — KS baseline | 0.01550 | 0.00859 | 0.03197 | 0.05303 | — |
| V1 — KS + per-segment bias (estimated on straights) | 0.01429 | 0.00497 | 0.03247 | 0.05419 | -0.00121 |
| V2 — Linear ST, prior C_α + bias | 0.01570 | 0.00364 | 0.03641 | 0.06273 | +0.00141 (regression) |
| V3 — Linear ST, fit C_α + bias | 0.01536 | 0.00368 | 0.03552 | 0.06134 | -0.00034 |
| V4 — V3 + Ridge residual LOSO on [v, |a_y|, |δ|, sign(δ̇)] | 0.01251 | 0.00385 | 0.02875 | 0.04822 | -0.00284 |

**Marginal-drop accounting** (greedy / sequential, one DoF per rung). Sum = -0.00298; V0→V4 = -0.00299. Closes to 0.3% — well inside the 15% bound.

## Honest regression flags

- **V2 is a regression on `all`** (+0.00141). Linear ST with the openpilot prior `C_α` over-steers vs measured at the high-`|a_y|` end. Improvement on straights is the bias-soak, not ST geometry.
- **V3 `C_α` fit pegs the upper bound** (scale = 2.00, `C_αf` = 573 kN/rad, `C_αr` = 712 kN/rad). The linear-ST steady-state form is mis-specified for this fleet, not just the priors — pegging at the bound means "the model wants infinite stiffness", i.e. it wants KS back. The 0.00034 drop from V2 to V3 is cosmetic.
- **V4 is the only sizeable lateral win** but it is a residual launderer; LOSO is honest, but the structural ladder bought us almost nothing on cornering; the cornering residual is non-linear and we should escalate to ST with proper tyre saturation (Pacejka) before trusting a model upgrade.

## Painful absence / surprise

- **No `a_y` ladder row** — `a_y_pred_mps2` and `a_y_resid_mps2` present in CSV; consistency check between the two truth channels skipped.
- **Straight-line dominates sample mix** (86%). The `all` column flatters straight-line bias fixes; steady and transient are the meaningful regimes — on those, V1→V4 only halves the transient RMSE.

## Rule-prevented near-misses

- Almost ran on Tesla (more segments). Skill matrix forbade it — no truth.
- Almost used `delta_wheel_deg`. Factor of `i_s`=17 averted.
- Almost reported in-fold Ridge RMSE as V4. Switched to LOSO.

## Surprise

KS already does straight-line yaw rate to 0.009 rad/s and the ST upgrade buys *worse* on cornering — the team's prior `C_α` is not calibrated for these tyres on these roads, and the fit pegs the bound, the documented "linear-ST form is wrong, not just the priors" signal. The next honest rung is Pacejka, not another linear-ST variant.

Files: `tools/lateral_ladder.py`.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleB-m3-agent-03",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-3/agent-03/REPORT.md",
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
