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

- agent_id: **angleB-m3-agent-04**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-3/agent-04/REPORT.md`

```markdown
# Module-3 / agent-04 (angle-B) — Lateral fidelity, Mach-E MK1

## Headline

On **FORD_MUSTANG_MACH_E_MK1** (120-segment sample, 306 535 valid samples), the lateral residual under test is `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads`. **A per-segment yaw-rate bias on straight-line samples — applied on top of KS — drops overall RMSE from 0.01326 to 0.01098 rad/s (-17%). Climbing the ladder to linear ST regresses.**

## Platform and clamping statement

- Platform: **FORD_MUSTANG_MACH_E_MK1** (Tesla excluded — no truth channel).
- `clamp_v_to_measured=True`, `clamp_delta_to_measured=True`. `v` and `δ` are inputs; `ψ̇` and `a_y` are predictions. Scored on `ψ̇` against `yaw_rate_meas_rads`.
- Sign sanity: `corr(δ_road, ψ̇_meas) = +0.937` on |δ| > 0.02 — convention correct.

## Variant ladder (RMSE of yaw-rate residual, rad/s)

Regime split: straight `|δ| < 0.01`; steady `|δ| ≥ 0.01 ∧ |δ̇| < 0.05`; transient `|δ| ≥ 0.01 ∧ |δ̇| ≥ 0.05`. Counts: all 306 535 / straight 267 811 / steady 31 811 / transient 6 913.

| Variant | all | straight | steady | transient | marginal (Δ from prev) |
|---|---:|---:|---:|---:|---:|
| V0 KS (baseline) | 0.01326 | 0.00936 | 0.02350 | 0.04310 | — |
| V1 KS + per-segment bias from straights | 0.01098 | 0.00494 | 0.02330 | 0.04360 | -0.00228 |
| V2 Linear ST, prior C_α | 0.01398 | 0.00777 | 0.02845 | 0.05102 | +0.00300 (regression) |
| V3 Linear ST, fit C_α + bias | 0.01192 | 0.00339 | 0.02680 | 0.05052 | -0.00206 |

V0 → V_last drop = -0.00133 rad/s. Sum-of-marginals = -0.00133 — exact match. Accounting scheme: cumulative-RMSE-drop per rung, `marginal = RMSE(V_{n-1}) − RMSE(V_n)`.

## What each change contributed

- **V1 (per-segment yaw-gyro bias from straight-line samples)** does essentially all the useful work: -0.00228 rad/s overall, -0.00442 rad/s on straights (which are 87% of samples). Cornering RMSE is unchanged at 0.02803 — a constant offset cannot help where the residual is signal-shaped.
- **V2 (linear ST, prior C_α)** is a **regression** in every regime. With Mach-E's openpilot priors, K_us comes out negative-ish/very small — the steady-state correction goes the wrong way at the speeds in this dataset relative to KS-and-bias.
- **V3 (ST with fit C_α + bias)** partially recovers the regression on straights (bias does it), but stays worse than V1 on every cornering regime. The optimiser **pegged C_αr at the 500 kN/rad upper bound** (α=1.40, C_αf=402k, C_αr=500k). Per the skill, pegging is itself the regression flag: the linear-ST functional form is wrong on this corpus, not the priors.

## Painful absence

No truth-channel transient acceleration to attribute residuals against. The transient bucket (6 913 samples, RMSE ~0.043–0.051 rad/s) is where the real gap lives, but with linear ST regressing there too, the next honest rung is non-linear tyre / slip model (Pacejka) or LOSO-CV residual learner — out of in-residual quick-fix scope. Also no per-segment IMU temperature / start-up channel.

## Near-misses

- Almost shipped V3 with α∈[0.3, 3.0]; fit went to α=3.0 (C_α ~860/1068 kN/rad), grossly unphysical. Re-bounding to skill-prescribed 50–500 kN/rad still pegs C_αr.
- Almost reported "+15% cornering improvement" by mixing V1 cornering RMSE with V0 straight RMSE before noticing the cornering bucket is unchanged V0↔V1.

## Surprise

KS, with a one-number-per-segment hack (mean straight-line offset), beats a properly-parameterised linear single-track on every regime including cornering. The story isn't "the model lacks slip" first — it's "the IMU has a per-route DC offset that swamps lateral-model error in the all-samples RMSE". Once that's removed, KS's remaining error is already what slip would address, and linear ST without a non-linear tyre cannot close it.

## Honest regression flags

- V2 worse than V1 in every regime (steady +21%, transient +17%, straight +57%) — flagged.
- V3 C_αr pegged at 500 kN/rad upper bound — flagged per skill.
- V3 still worse than V1 on cornering — flagged.
- No LOSO-CV variant attempted; any residual-learner result would be dishonest in-fold and was therefore not climbed.

Files: `tools/lateral_ladder.py`.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleB-m3-agent-04",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-3/agent-04/REPORT.md",
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
