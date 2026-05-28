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

- agent_id: **angleA-m3-agent-02**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-3/agent-02/REPORT.md`

```markdown
# Module-3 / agent-02 — Lateral-fidelity variant ladder (Mach-E)

## Setup

- Platform scored: **FORD_MUSTANG_MACH_E_MK1** (315 segments, 913 626 rows at 50 Hz).
- `yaw_rate_meas_rads` is the **measured** truth channel decoded from Ford CAN gyro — not a prediction, not a clamped self-consistency state.
- Operating contract: under `clamp_v_to_measured=True` and `clamp_delta_to_measured=True`, `v_mps` and `delta_road_rad` are **inputs (clamped)** at every step; `yaw_rate_pred_rads` and `a_y_pred_mps2` are the **predicted** lateral channels. Metric: `RMSE(yaw_rate_pred − yaw_rate_meas)` partitioned by regime.
- Regime mask (held constant, via `triage.regime_mask`):
  - straight: `|δ_road| < 0.01 rad`
  - steady cornering: `|δ_road| ≥ 0.01` ∧ `|dδ/dt| < 0.05 rad/s`
  - transient cornering: `|δ_road| ≥ 0.01` ∧ `|dδ/dt| ≥ 0.05 rad/s`
- Sign check: `corr(δ_road, ψ̇_meas) = +0.702` on cornering samples. Convention is correct.
- Attribution scheme: **strict marginal** in fixed order V0→V1→V2→V3→V4. Total V0→V4 drop = 0.00072; sum of marginals = 0.00071 (≈1.5% rounding gap, within 15% bar).

## Variant ladder

| Variant | Overall RMSE (rad/s) | Straight | Steady corner | Transient corner | Marginal drop (overall) |
|---|---:|---:|---:|---:|---:|
| V0 — baseline (`yaw_rate_resid_rads` as-is)                                    | 0.01613 | 0.00877 | 0.03173 | 0.05680 | — |
| V1 — KS recalibrated + per-segment straight-line yaw-gyro bias                  | 0.01469 | 0.00493 | 0.03168 | 0.05730 | -0.00143 |
| V2 — Linear ST, prior `C_α` (openpilot carParams) + same per-seg bias           | 0.01551 | 0.00339 | 0.03430 | 0.06277 | +0.00082 (regression) |
| V3 — Linear ST, fit `C_α` (bounded 5e4–5e5 N/rad) + same per-seg bias           | 0.01564 | 0.00349 | 0.03462 | 0.06307 | +0.00013 (regression) |
| V4 — Ridge residual learner on V3 residuals, leave-one-segment-out CV           | 0.01541 | 0.00357 | 0.03414 | 0.06179 | -0.00023 |

## Discussion

- **V1 carries the whole improvement.** Stock `yaw_rate_pred_rads` already uses canonical `L = 2.984 m` (max recompute diff = 3e-6 rad/s); the V1 lift is entirely **per-segment yaw-gyro bias subtraction** (mean 0.0007 rad/s, std 0.0070, range [-0.024, +0.019]). Cuts straight-regime RMSE almost in half (0.00877 → 0.00493).
- **V2 is a regression on this fleet — physical cause.** Linear ST with openpilot's prior `C_αf=286 551, C_αr=355 912 N/rad` makes steady and transient cornering RMSE worse (0.03430 vs 0.03168; 0.06277 vs 0.05730). The ST prior is *stiffer* than the Mach-E tyres want, so it under-predicts the gain shrinkage at high `|a_y|` — exactly the regression the variant catalogue calls out. KS, having no slip, accidentally matches better.
- **V3 confirms the prior is the problem, not the solver.** Default L-BFGS-B from `triage.fit_c_alpha` lands at `(1.5e5, 1.5e5)` (its init) with loss flat there. A multi-start grid finds the true minimum **pegged at the upper bound (5e5, 5e5) N/rad** — the fitter wants ST as stiff as possible, degenerate toward KS-like behaviour. The ST functional form simply does not fit these data. Reported as regression.
- **V4 is a marginal recovery.** Ridge on `[v, |a_y|, |δ|, sign(δ̇)]` with LOO CV claws back 0.00023 rad/s OOF against V3 — real, but smaller than V1's win and not enough to recover even V1's level. Honestly, **V1 is the variant to ship**.

## Recommendation

Ship **V1**. The ST upgrade does *not* improve lateral fidelity on this Mach-E fleet at the openpilot prior, and the in-bounds fit is degenerate. The bias subtraction in V1 is the only honest improvement available with the components in this harness.

## Limitations

- No non-linear ST / Pacejka rung available — V3's pegging suggests the slip-stiffness *relationship* is what needs to change, not the magnitudes of `C_α`. Harness offers no rung for that.
- No `evals/` directory in this module — could not auto-validate the report.

Files: `out/ladder_results.json`, `out/ladder_summary.txt`, `out/v1_bias_per_segment.json`, `tools/run_ladder.py`.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleA-m3-agent-02",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-3/agent-02/REPORT.md",
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
