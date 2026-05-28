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

- agent_id: **angleB-m3-agent-02**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-3/agent-02/REPORT.md`

```markdown
# Module-3 / agent-02 (angle-B) — Lateral fidelity ladder (Mach-E)

## Headline

**Platform: FORD_MUSTANG_MACH_E_MK1** (315 segments, ~9.4 M samples at 50 Hz). Speed-known, lateral-only contract: `v` and `δ` clamped to measured; the model predicts `ψ̇`. Scored against `yaw_rate_meas_rads`. Sign sanity `corr(δ_road, ψ̇_meas | cornering) = +0.702` — convention OK.

## Variant ladder

Yaw-rate RMSE (rad/s), same segments, same regime mask:

| Variant | Name | all | straight | steady | trans | marginal Δ |
|---|---|---:|---:|---:|---:|---:|
| V0 | KS, as shipped | 0.0161 | 0.0088 | 0.0317 | 0.0569 | — |
| V1 | V0 + per-seg straight-line yaw bias removal | 0.0147 | 0.0049 | 0.0317 | 0.0574 | -0.0014 |
| V2 | Linear ST, prior C_α (+ V1 bias) | 0.0155 | 0.0034 | 0.0343 | 0.0629 | +0.0008 (regression) |
| V3 | Linear ST, fit C_α (bounded 50–500 kN/rad) | 0.0151 | 0.0034 | 0.0333 | 0.0616 | -0.0004 |
| V4 | V3 + Ridge residual learner, **LOSO CV** | 0.0149 | 0.0035 | 0.0329 | 0.0604 | -0.0002 |

Total V0 → V4 drop = **0.0012 rad/s (7.5%)**. Sum of marginal drops = 0.0012 — within-15% reconciliation passes. Accounting scheme: **ladder-order marginal**.

V3 fit: `C_αf = 158 261 N/rad`, `C_αr = 138 286 N/rad` — both well inside physical range, **much softer than openpilot priors** (286.5k / 355.9k). Not pegged at any bound.

## Painful absence

Almost all available headroom lives in V1 (a per-segment yaw-gyro bias, not a model upgrade). The fancy stuff — ST priors, fit C_α, residual learner — together adds **0.0002 rad/s** on top of V1. The team's KS-vs-ST debate is being held about a 1.5% effect; the real win is an IMU offset correction that any rung can absorb.

## Rule-prevented near-misses

- Skill warned not to score Tesla (no truth) → used Mach-E.
- Skill warned `delta_wheel_deg` vs `delta_road_rad` (factor-15 trap) → consumed `delta_road_rad`.
- Ladder discipline forced LOSO CV on V4; in-fold Ridge would have spuriously closed the residual.
- Same segment set + same regime mask across rows → marginal-drop sum reconciles.

## Honest regression flag

**V2 regresses against V1 on cornering** (steady 0.0317 → 0.0343, transient 0.0574 → 0.0629). Physical reason: openpilot prior C_α is too stiff for these tyres / pavement; linear-ST steady-state gain under-rotates the yaw response. V3 confirms by fitting softer stiffnesses (~55% of prior front, ~39% of prior rear) and partially recovering — but not enough to beat V1's gyro-bias correction on its own.

## Surprise

On this dataset, **KS is not the lateral problem**. The dominant error in lateral fidelity is a static per-segment yaw-rate bias (likely IMU gyro offset accumulating), not the missing slip in the kinematic model. Climbing the CommonRoad fidelity ladder past KS pays diminishing single-digit-percent dividends until tyre slip starts dominating, which on this segment mix it does not. The C_α fit being substantially softer than openpilot's prior is a quiet finding: the canonical numbers under-predict actual yaw gain at modest steering inputs.

Files: `out/ladder.json`, `tools/lateral_ladder.py`.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleB-m3-agent-02",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-3/agent-02/REPORT.md",
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
