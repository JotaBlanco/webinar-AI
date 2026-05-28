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

- agent_id: **angleA-m2-agent-01**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-2/agent-01/REPORT.md`

```markdown
# Module-2 / agent-01 — Lateral fidelity report

**Platform scored:** Ford (Mach-E MK1 + F-150 Lightning MK1), 545 segments total. The `yaw_rate_meas_rads` and `a_lat_meas_mps2` columns are **measured truth** decoded from rlog CAN, not predictions or self-consistency.

**Speed-known contract honoured.** `v_mps` and `delta_road_rad` are **clamped** inputs in every variant; the KS integrator's own `v`/`δ` state updates are overwritten by measurement each step. The **predicted** channel under test is `yaw_rate_pred_rads`.

**Headline result:** Overall yaw-rate RMSE dropped from **0.01804 rad/s (V0) to 0.01568 rad/s (V4) — a 13.1% reduction**. Most of the drop lives in cornering (steady 0.0247 → 0.0213; transient 0.0465 → 0.0422).

## Variant ladder

Same Ford segment set, same regime mask, marginal-drop accounting on global RMSE.

| Variant | Straight | Steady | Transient | Overall | Δ vs prior | Description |
|---------|---------:|-------:|----------:|--------:|-----------:|-------------|
| V0 baseline   | 0.00789 | 0.02473 | 0.04654 | 0.01804 | —         | `yaw_rate_resid_rads` as-is |
| V1 gyro-bias  | 0.00644 | 0.02447 | 0.04641 | 0.01752 | -0.00051  | Subtract per-segment yaw-rate bias estimated on straight stationary-wheel slices |
| V2 LPF δ      | 0.00642 | 0.02446 | 0.04639 | 0.01751 | -0.00001  | 3 Hz Butterworth on `delta_road_rad` before kinematic prediction |
| V3 lag        | 0.00630 | 0.02452 | 0.04534 | 0.01733 | -0.00018  | Align meas to pred by global lag (80 ms / 4 samples) |
| V4 understeer | 0.00617 | 0.02125 | 0.04216 | 0.01568 | -0.00165  | `ψ̇ = ψ̇_kin / (1 + K_us·v²/L)`, K_us fit per platform |

- **Regimes:** straight = `|δ_road|<0.005 ∧ |a_lat|<0.5`; transient = cornering ∧ `|dδ/dt|≥0.02 rad/s`; steady = remaining cornering.
- **Accounting:** strict marginal in fixed order V0→V1→V2→V3→V4. Marginal drops sum to 0.00236, matching total V0−V4.
- **Fitted parameters:** lag = 80 ms; K_us = −3.1e-4 (Mach-E), +4.1e-3 (F-150).

## Limitations

- No held-out validation split. K_us fit globally and reported on the same data — no train/test discipline declared. V2 LPF kept despite ~0 marginal because the only way to know it doesn't *hurt* a future segment is to test on one.
- Regime thresholds chosen by inspection.

## Notes

- **No regressions observed.**
- Mach-E fitted K_us is **negative** (small) while Lightning is clearly positive. Textbook expectation is K_us > 0 for both. Likely Mach-E sits in the linear-tyre regime at these speeds and the bigger residual driver is steering-ratio/compliance, not slip. A single-platform K_us would have *added* error on Mach-E.

Files: `out/run_ladder.py`, `out/results.json`, `out/results.csv`.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleA-m2-agent-01",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-2/agent-01/REPORT.md",
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
