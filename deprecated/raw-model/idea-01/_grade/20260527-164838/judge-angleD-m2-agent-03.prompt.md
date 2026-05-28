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

- agent_id: **angleD-m2-agent-03**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-2/agent-03/REPORT.md`

```markdown
# REPORT — webinar-angle-D / module-2 / agent-03

**Task:** Improve KS lateral (yaw-rate) prediction on Ford and attribute the gains.
**Platform scored:** `FORD_MUSTANG_MACH_E_MK1` (Mach-E). Truth channel: `yaw_rate_meas_rads` is **measured** from the rlog IMU (Ford party DBC).
**Sample:** 25 segments, 72,477 rows (seeded sample of 315 Mach-E sims).
**Operating contract:** speed-known, lateral-only (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Residual under test = `yaw_rate_resid = pred − meas`.

## Variant ladder

| Variant | Overall RMSE (rad/s) | Straight | Steady cornering | Transient | Δ vs prev (overall) |
|---|---:|---:|---:|---:|---:|
| V0 — CSV baseline (`yaw_rate_pred_rads`) | 0.01277 | 0.00924 | 0.01699 | 0.04689 | — |
| V1 — KS w/ canonical `L` + per-segment yaw-gyro bias on straights | **0.01133** | **0.00627** | 0.01702 | 0.04819 | **−0.00144 (−11.3%)** |
| V2 — Linear ST, prior `C_α` (286.6k / 355.9k N/rad) + per-seg bias | 0.01204 | 0.00436 | 0.02083 | 0.05268 | +0.00071 (worse) |
| V3 — Linear ST, fit `C_α` (bounded 5e4–5e5 N/rad) + per-seg bias | 0.01224 | 0.00443 | 0.02134 | 0.05309 | +0.00020 (worse) |
| V4 — V3 + Ridge residual learner on `[v, \|a_y\|, \|δ\|, sign(δ̇)]` (LOO) | 0.01273 | 0.00458 | 0.02252 | 0.05423 | +0.00049 (worse) |

Regime counts: straight 59,103 / steady 11,845 / transient 1,529.

## Attribution

- **V1 (canonical-L KS + per-segment straight-regime yaw bias)**: −0.00144 rad/s overall (−11.3%). Effectively a per-segment yaw-gyro zero-offset correction. Straight RMSE falls 32% (0.00924 → 0.00627); steady and transient are essentially unchanged. This is the only variant that *helps*.
- **V2 (linear ST, prior Cα)**: +0.00071 rad/s. The understeer-gradient denominator `1 + K_us·v²` is non-zero (Mach-E is rear-biased: `l_r·C_αr − l_f·C_αf > 0`), so it slightly attenuates yaw vs KS at highway speeds. With the truth channel matching KS well already, attenuation = regression.
- **V3 (linear ST, fit Cα)**: +0.00020 vs V2. The loss surface is monotone toward Cα → ∞ (which is exactly KS). `fit_c_alpha` (L-BFGS-B from `x0=[1.5e5,1.5e5]`) returns the initial guess because the local gradient is shallow; a coarse grid search confirms the bounded optimum sits at (5e5, 5e5) — i.e. the optimiser wants to *become* KS, but is held inside the prior box. Bottom line: there's no linear-ST sweet spot for Mach-E on this corpus.
- **V4 (Ridge residual learner, LOO)**: +0.00049 vs V3. The residuals look segment-specific (driver style, road grade, suspension warm-up) and don't generalise across segments under leave-one-out CV. Ridge with `[v, |a_y|, |δ|, sign(δ̇)]` adds noise on held-out segments.

## What actually fixed things

Stock `yaw_rate_pred_rads` in `sim.csv` already equals the canonical KS formula `(v/L)·tan(δ)` with the openpilot Mach-E `L=2.984 m` (corr=1.0 vs recomputation, RMSE diff ≈1e-7). So "KS recalibration" is a no-op on this corpus. The *real* gain in V1 is the **per-segment yaw-gyro bias subtraction on straight-line samples** (`|δ_road| < 0.01 rad`). That single offset accounts for the entire −11.3% improvement and tells us the dominant lateral residual is a near-DC gyro-mount/zero bias, not a slip-dynamics effect.

## Sign-error spot-check

`corr(δ_road, ψ̇_meas)` on cornering segments: 0.98–0.99 across spot-checked routes. No sign error.

## Caveats / limitations

- Scored on a 25-segment seeded sample (seed=0) of 315 Mach-E segments — not the full corpus.
- Transient regime is only 2% of samples (1,529 rows). Its RMSE moves but the row count is too low for confident attribution.
- `fit_c_alpha` as shipped relies on L-BFGS-B from a single seed; on this corpus that's effectively a no-op. A multi-start or DE pass would resolve it but wouldn't change the conclusion — the linear-ST rung is the wrong tool here.
- F-150 Lightning not scored. Lateral truth channel exists for it too; would likely show the same picture (bias-dominated) but heavier mass.

## Most painful missing component

`references/` with a one-line note that `yaw_rate_pred_rads` in the published CSV is already canonical KS. The skill currently makes V1 sound like a re-derivation upgrade; in reality V1's whole value is the bias subtraction. Five minutes lost confirming this by hand.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleD-m2-agent-03",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-2/agent-03/REPORT.md",
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
