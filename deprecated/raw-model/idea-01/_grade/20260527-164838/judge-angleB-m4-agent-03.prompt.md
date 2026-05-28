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

- agent_id: **angleB-m4-agent-03**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-4/agent-03/REPORT.md`

```markdown
# Module-4 / agent-03 (angle-B) — Lateral fidelity

## Headline

Only one variant of four improved on KS; the rest regressed. On 80 Ford Mach-E segments (203 303 samples, v ≥ 2 m/s), overall yaw-rate-residual RMSE went 0.01451 → 0.01262 rad/s with **per-segment IMU yaw-gyro bias removal (V1, -13%)**, and got worse with every cornering-model upgrade attempted.

## Stated platform & contract

- Platform: `FORD_MUSTANG_MACH_E_MK1` (Tesla excluded — no truth channel).
- Clamped inputs: `v_mps`, `delta_road_rad`. Predicted output: `yaw_rate_pred_rads`. Residual under test: `yaw_rate_resid_rads` (pred − meas).
- Sign sanity: `corr(δ_road, ψ̇_meas) = +0.934` on corners (positive → OK).

## Variant ladder, per-regime RMSE (rad/s), strict marginal accounting in fixed order

| Variant | overall | straight | steady | transient | marginal |
|---|---|---|---|---|---|
| V0 baseline | 0.01451 | 0.00890 | 0.02706 | 0.04893 | — |
| V1 IMU yaw-gyro bias / seg | 0.01262 | 0.00474 | 0.02673 | 0.04884 | **-0.00189** |
| V2 lin-ST steady, prior C_α | 0.02035 | 0.01415 | 0.03652 | 0.06065 | **+0.00773** (regression) |
| V3 lin-ST steady, fit C_α LOSO | 0.02188 | 0.01787 | 0.03360 | 0.05538 | **+0.00153** (regression) |
| V4 Ridge residual LOSO | 0.02143 | 0.01836 | 0.03004 | 0.05168 | -0.00045 |

Total V0→V4 = +0.00692 (worse). Sum of marginals = total exactly. Attribution: **strict marginal in fixed lock-step V0→V4** — each row's marginal is attributed to the rung that added the DoF.

## Painful absence

KS is not the lateral-fidelity bottleneck on this dataset — IMU yaw-gyro offset is. The variant the fidelity ladder treats as "cheapest" (per-segment bias) is the only one that delivered. The classical KS → linear-ST upgrade regressed. The honest path forward is **linear-ST dynamic (not steady-state)** or non-linear tyre; the steady-state gain rung does not earn its keep on this car.

## Near-misses (regression flags, honestly logged)

- V2 (prior C_α) over-states understeer for the Mach-E vs the openpilot prior; SS-ST yaw rate is ~30% short.
- V3 LOSO fit inverted the C_αf/C_αr ratio (median 394k / 257k vs prior 287k / 356k) and clustered C_αf at 392–400k — upper-physical band. Per skill: this is the regression flag that says **the linear-ST steady-state form is misspecified**, not just its priors.
- V4 (Ridge LOSO) reclaimed 0.00045 of V3's 0.00926 regression — linear residual learner cannot launder a misspecified steady-state baseline.

## Surprise

The straight regime, not the cornering regime, contains the dominant fix. KS is geometric and predicts ~0 yaw rate on straights; any non-zero straight-regime residual is necessarily sensor bias, not model gap. That 13% overall RMSE drop is essentially free.

## RPI artifacts

- Research: `rpi/runs/20260527-155852/research.md`
- Plan (locked): `rpi/runs/20260527-155852/plan.md`
- Implement notes: `rpi/runs/20260527-155852/implement-notes.md`
- Code: `tools/run_ladder.py`. Output: `out/ladder.csv`.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleB-m4-agent-03",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-4/agent-03/REPORT.md",
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
