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

- agent_id: **angleB-m4-agent-01**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-4/agent-01/REPORT.md`

```markdown
# Module-4 / agent-01 (angle-B) — Lateral fidelity ladder

## Headline

On 60 Mach-E segments (~180k samples at 50 Hz) of clamped-(v,δ) KS, the honest win is **V1 per-segment IMU yaw-gyro bias removal: -13% overall RMSE (0.01214 → 0.01055 rad/s), -41% on straight (0.00851 → 0.00506)**. Every rung above V1 regressed; the ladder's net V0→V4 drop is **negative** (-0.00122). Shipping the partial and reporting the regression flags rather than swapping variants.

## Platform / contract

Ford Mustang Mach-E MK1 (the only platform with truth ψ̇ and a_y; Tesla has no IMU truth). `v` and `δ` clamped to measured; residual under test is `yaw_rate_pred_rads − yaw_rate_meas_rads`. Sign sanity passed: `corr(δ_road, ψ̇_meas | cornering) = +0.927`.

## Variant ladder (same segments, same mask, RMSE rad/s)

| # | Variant | overall | straight | steady | transient | marginal Δ overall |
|---|---|---|---|---|---|---|
| V0 | baseline KS | 0.01214 | 0.00851 | 0.02520 | 0.04892 | — |
| V1 | + per-seg IMU bias | **0.01055** | **0.00506** | 0.02602 | 0.05119 | **-0.00159** |
| V2 | + linear ST, prior C_α | 0.01248 | 0.00335 | 0.03425 | 0.06367 | +0.00193 (regress) |
| V3 | + linear ST, fit C_α | 0.01550 | 0.00569 | 0.04286 | 0.07162 | +0.00302 (regress, **C_α pegged at lower bound 50 kN/rad** — linear-ST form is wrong, not just priors) |
| V4 | + ridge residual, LOSO | 0.01336 | 0.00563 | 0.03541 | 0.06249 | -0.00214 (recovers some V2/V3 loss but never beats V1) |

Marginal drops sum to total V0→V4 (consistency 100%, lock-order strict-marginal).

## Painful absence

No banking/camber channel. The per-segment "bias" V1 removes is a mix of true IMU offset and steady road-camber on straight stretches; that's why applying V1 outside straight nudges cornering RMSE up +3-5%.

## Near-miss

V2 wins **on straight** (-34% vs V1) because at small δ the ST gain is slightly smaller than KS's `tan(δ)/L`. But V2 ships KS-truth divergence in the wrong direction on cornering — the openpilot prior K_us shrinks ψ̇ when truth is, if anything, **above** KS. V3 confirms it: 1-D fit drives K_us negative (oversteer-leaning) and pegs both C_α at the 50 kN/rad floor.

## Surprise

The cleanest, cheapest fix is also the only fix that worked: 1 scalar per segment. The whole tyre-model rung is mis-pointed on this prior set; before any honest ST rung, a **direction-of-K_us probe** belongs in Research, not in V2.

## RPI artifacts

- Research: `rpi/runs/20260527T135842Z/research.md`
- Plan (locked): `rpi/runs/20260527T135842Z/plan.md`
- Implement notes: `rpi/runs/20260527T135842Z/implement-notes.md`
- Numerical artifact: `out/ladder.json`
- Tool: `tools/lateral_ladder.py`

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleB-m4-agent-01",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-4/agent-01/REPORT.md",
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
