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

- agent_id: **angleD-m2-agent-02**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-2/agent-02/REPORT.md`

```markdown
# Lateral fidelity ladder — webinar-angle-D / module-2 / agent-02

Platform: **Ford Mustang Mach-E (MK1)**. `yaw_rate_meas_rads` is the **measured** truth channel (IMU-decoded). 25 of 315 Mach-E segments sampled (seed=42), 72,485 rows. Operating contract: speed- and steering-clamped, lateral-only.

## Headline

**Overall yaw-rate RMSE dropped from 0.01178 rad/s (V0) to 0.00909 rad/s (V1) — a 22.8% reduction.** All subsequent ladder rungs (V2–V4) made things slightly worse on this dataset.

## Variant ladder (RMSE in rad/s)

| Variant | Overall | Straight | Steady | Transient | Δ vs prev | Attribution |
|---|---|---|---|---|---|---|
| V0 baseline (pre-computed resid) | 0.01178 | 0.00913 | 0.02175 | 0.03437 | — | reference |
| V1 KS recalib + per-segment gyro bias | **0.00909** | **0.00498** | 0.02110 | 0.03360 | **−0.00268** | **straight-line gyro bias removal — 100% of total gain** |
| V2 Linear ST, prior C_α | 0.00981 | 0.00307 | 0.02599 | 0.03921 | +0.00072 | helps straights further, hurts cornering (overconfident slip model) |
| V3 Linear ST, fit C_α | 0.00997 | 0.00318 | 0.02640 | 0.03968 | +0.00016 | fit landed at C_αf=C_αr=150k (L-BFGS-B stuck near x0); grid search gives 400k/400k with RMSE 0.01167 — fit gives no meaningful lift over KS |
| V4 Ridge residual learner on V3 | 0.00971 | 0.00336 | 0.02508 | 0.03919 | −0.00026 | LOO oof_rmse=0.00971; recovers a little but cannot undo V2's cornering damage |

Best overall: **V1**. Best on straight regime: **V2**. No variant wins on cornering — all are worse than V0 there.

## Most painful missing component

**`evals/`** — a frozen held-out split with regime-stratified scoring. Without it I had to roll my own segment sampling (seed=42, n=25), bias-correct in-sample, and trust LOO for V4 only. There is no protection against V1's bias-correction overfitting to per-segment quirks, and no way to know whether V2's cornering regression is a real model failure or sampling noise. It cost me ~5 min of redundant diagnostic loops and leaves the ranking confidence-poor.

## What the rules prevented

I almost cross-referenced the Tesla `sim.csv` schema to confirm `yaw_rate_meas_rads` is genuinely absent there (skill claims it is) but `TESLA_MODEL_3/` is under `data/` and the skill is explicit about Ford-only — proceeded on assumption.

## Most surprising thing

**The "ladder" is misnamed.** On Mach-E, the entire correlation improvement comes from removing a per-segment yaw-gyro DC bias on straight-line samples. The linear-ST slip model with both prior and fit C_α gives essentially zero lift over plain KS — because mean |δ_road| ≈ 0.008 rad on real driving data, the slip-angle correction K_us·v²·δ is dwarfed by sensor calibration error. The fit_c_alpha helper looked broken (returned exactly x0), but grid search confirmed it: the loss surface is flat in (C_αf, C_αr) at the priors. The residual-learner rung partially recovers what V2 destroyed but is net-negative vs V1. **Gyro bias > slip dynamics** on this corpus.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleD-m2-agent-02",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-2/agent-02/REPORT.md",
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
