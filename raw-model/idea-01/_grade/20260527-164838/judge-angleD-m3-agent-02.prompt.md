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

- agent_id: **angleD-m3-agent-02**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-3/agent-02/REPORT.md`

```markdown
# REPORT.md — lateral-fidelity-triage on Mach-E (module-3 / agent-02)

- **Platform:** `FORD_MUSTANG_MACH_E_MK1` (Mach-E MK1).
- **Truth channel:** `yaw_rate_meas_rads` is **measured** truth (decoded Ford IMU from rlog).
- **Contract:** `v` and `δ` are **clamped to measured** at every step (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Speed-state agreement is therefore not a metric here; only lateral residual is.
- **Residual under test:** `yaw_rate_pred_rads − yaw_rate_meas_rads`, in rad/s.
- **Segment set:** 30 Mach-E `sim.csv` files (evenly sampled from 315 available), 87 040 rows total.
- **Regime mask:** straight `|δ|<0.01 rad`; steady `|δ|≥0.01 & |dδ/dt|<0.05 rad/s`; transient `|δ|≥0.01 & |dδ/dt|≥0.05`.
- **Accounting:** strict marginal, fixed order V0→V1→V2→V3→V4. Sum of marginal drops = total V0→V4 drop (0.00288 rad/s); 0 % off — within the 15 % tolerance.
- **Best variant:** **V2** (Linear ST with prior `C_α`). V3 and V4 are regressions vs V2 and are reported as such.
- **Sensor gate:** `python3 skills/lateral-fidelity-triage/sensor.py out/best_variant_V2.csv` → both checks PASS (`corr(pred,meas)=0.998` on cornering; `RMSE=0.00821 ≤ V0=0.01143`).

## Variant ladder (RMSE of yaw-rate residual, rad/s)

| Variant | Overall | Straight | Steady cornering | Transient cornering | Marginal Δ (overall) | Notes |
|---|---|---|---|---|---|---|
| V0 — baseline (as-is `yaw_rate_resid_rads`) | 0.01143 | 0.00962 | 0.01719 | 0.02851 | — | No preprocessing. |
| V1 — KS recalibrated + per-segment straight-line gyro bias | 0.00888 | 0.00598 | 0.01669 | 0.02705 | −0.00255 (−22 %) | Canonical L=2.984 m; bias removed where `|δ|<0.01`. |
| V2 — Linear ST, prior `C_αf=286 551`, `C_αr=355 912` (openpilot-canonical), v_min=2 m/s KS fallback | **0.00821** | **0.00318** | 0.01787 | 0.03244 | −0.00068 (−8 %) | Best overall. Improves straight, mildly worsens cornering. |
| V3 — Linear ST with fit `C_α` | 0.00853 | 0.00333 | 0.01870 | 0.03293 | +0.00032 (+4 %) | **Regression.** L-BFGS-B did not move from `x0=(1.5e5,1.5e5)` — not pegged at upper bound, but evidently stuck on a flat region of the loss surface for this subset. The skill's pegged-Cα detector does not catch a stuck-at-initial-guess failure. |
| V4 — Ridge residual learner on `[v, |a_y|, |δ|, sign(δ̇)]`, leave-one-segment-out | 0.00855 | 0.00394 | 0.01836 | 0.03113 | +0.00002 (+0 %) | **Regression.** OOF Ridge cannot beat V3 out-of-fold; per the skill, V3 (already a regression) and V4 are both rejected. |

## Per-variant contribution to improvement

- V1 (KS recalibration + straight-line bias removal): **−2.55 mrad/s RMSE** — 88 % of the total improvement.
- V2 (linear ST with prior `C_α`): **−0.68 mrad/s RMSE** — 23 % more, but concentrated on straight-line samples.
- V3 (fit `C_α`): **+0.32 mrad/s** — regression; optimiser stuck at initial guess `(1.5e5, 1.5e5)` for both axles, which is below the openpilot-canonical prior Mach-E uses, so the V2→V3 step effectively softens the tyres without justification.
- V4 (Ridge LOO residual learner): **+0.02 mrad/s** — null/regression; OOF RMSE 0.00913 > V3 in-set, fails the "must beat V3 out-of-fold" gate.

## Best variant shipped

V2 (Linear ST, prior `C_αf=286 551` N/rad, `C_αr=355 912` N/rad) + per-segment straight-line yaw-gyro bias removal, with v_min=2 m/s KS fallback. Written to `out/best_variant_V2.csv`. Sensor PASS.

## Honest caveats

- V2 improves *overall* RMSE only because straight-line samples dominate. On cornering subsets, V2 is **worse** than V1: steady 0.01787 vs 0.01669 (+7 %), transient 0.03244 vs 0.02705 (+20 %). If the downstream consumer cares mostly about cornering, **ship V1**, not V2.
- V3 was not pegged at the upper bound (`(1.5e5, 1.5e5)`), but the optimiser did not move from the initial guess. This is a failure mode the v0.5 pegged-Cα rule does not catch. A `success` flag, gradient diagnostic, or multi-start fit should be added in v0.6.
- The skill mandates Ford for measured truth — confirmed. Tesla segments were excluded.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleD-m3-agent-02",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-3/agent-02/REPORT.md",
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
