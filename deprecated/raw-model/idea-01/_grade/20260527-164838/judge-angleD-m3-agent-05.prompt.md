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

- agent_id: **angleD-m3-agent-05**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-3/agent-05/REPORT.md`

```markdown
# REPORT — Lateral-fidelity triage on Ford Mustang Mach-E (MK1)

- **Platform:** `FORD_MUSTANG_MACH_E_MK1` (Mach-E). `yaw_rate_meas_rads` is **measured** truth from the Ford party DBC in the rlog (IMU yaw rate).
- **Operating contract:** `v` and `δ` are **clamped to measured** under the speed-known contract (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Lateral-only metric: `yaw_rate_pred_rads − yaw_rate_meas_rads`.
- **Segment set:** first 20 Mach-E `sim.csv` files under `data/sim/segments/FORD_MUSTANG_MACH_E_MK1/` (sorted), 57,979 rows total. Regime split: straight 55,076 / steady 1,901 / transient 1,002.
- **Attribution scheme:** strict marginal, fixed order V0→V1→V2→V3→V4 (per skill v0.5).
- **Sensor:** `sensor.py` PASSED on `out/best_V1.csv` — corr(pred, meas) on cornering = 0.996; RMSE(candidate) = 0.01368 ≤ V0 = 0.01575.

## Variant ladder (RMSE in rad/s, lower is better)

| Variant | Overall | Straight | Steady | Transient | Marginal vs prev | Note |
|---|---|---|---|---|---|---|
| V0 baseline | 0.01575 | 0.01095 | 0.04411 | 0.06379 | — | as-is `yaw_rate_resid_rads` |
| V1 KS + per-seg yaw-gyro bias | **0.01368** | **0.00662** | 0.04522 | 0.06738 | **−0.00207** | wins overall and on straights |
| V2 linear ST, prior Cα | 0.01606 | 0.00351 | 0.06072 | 0.08514 | +0.00238 | **regression overall**: prior Cα over-stiffens cornering response |
| V3 linear ST, fit Cα (L-BFGS-B, bounds 5e4–5e5) | 0.01616 | 0.00363 | 0.06108 | 0.08553 | +0.00011 | **regression**: fit returned x0 (Cf=Cr=1.5e5) — solver did not move from initial guess; pegged-bound check did not fire |
| V4 Ridge LOO residual learner on V3 | 0.01529 | 0.00372 | 0.05586 | 0.08271 | −0.00088 | partial recovery; still worse than V1 |

- Marginal sum V0→V4 = +0.00046; total drop V0→V4 = +0.00046 (within 15% by coincidence — regressions and the V4 recovery nearly cancel).
- V1 is the best ship-ready variant overall and on straights (which are 95% of the corpus).
- V2/V3/V4 do beat V1 on the **straight** regime in isolation, but only because they shrink already-small straight residuals at the cost of large cornering error.

## Bullets

- Dominant fix was V1's per-segment yaw-gyro bias on straight-line samples: straight RMSE 0.01095 → 0.00662 (−39.5%).
- V2 prior Cα (Mach-E openpilot-canonical: Cf=286,551, Cr=355,912) makes steady-state gain too stiff for this Mach-E corpus → cornering RMSE roughly doubles.
- V3 fit failure mode: `scipy.optimize.minimize(L-BFGS-B)` exited at the initial guess `(1.5e5, 1.5e5)`. The pegged-at-upper-bound check (v0.5) does not detect a stationary-at-x0 outcome. Flagged here as a regression with cause: solver convergence failure on a near-flat loss surface dominated by straight samples.
- V4 LOO residual learner partially recovers from V3 (overall 0.01616 → 0.01529) but never beats V1 → per skill rule, V4 ships as a regression.
- No second markdown table per v0.5 reporting rule.
- Sensor was run as the final gate on `out/best_V1.csv` and passed both checks.

## Shipped variant

**V1** — KS yaw-rate using canonical `L = 2.984 m` plus per-segment mean residual subtracted on `|δ_road| < 0.01 rad` samples.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleD-m3-agent-05",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-3/agent-05/REPORT.md",
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
