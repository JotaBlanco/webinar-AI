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

- agent_id: **angleE-m3-agent-02**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-3/agent-02/REPORT.md`

```markdown
# REPORT — module-3 / agent-02 (universal agent + skill tier)

## Platform & contract

- Platform: `FORD_MUSTANG_MACH_E_MK1` (default per skill, task did not specify)
- Truth channel: `yaw_rate_meas_rads` is the measured ground truth in each Ford `sim.csv`.
- Inputs `v` and `δ` are clamped to measured (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Speed-state agreement is zero by construction and is not the metric. Only the lateral residual (RMSE of `pred − meas`) is reported.
- Segments loaded: 315 Ford Mach-E segments, 913,626 rows.
- Attribution scheme: strict marginal, fixed order V0→V1→V2→V3. Marginal drop = `RMSE(V_{i-1}) − RMSE(V_i)`. Sum of marginals reconciles to total drop within 0.0% (well under the 15% tolerance the skill mandates).

## Variant ladder (RMSE of yaw-rate residual, rad/s)

| variant | overall | straight | steady   | transient | marginal drop (overall) | notes |
|---------|---------|----------|----------|-----------|-------------------------|-------|
| V0  baseline (CSV column)         | 0.016127 | 0.008768 | 0.031733 | 0.056797 | —          | as-shipped residual |
| V1  KS recalib + per-seg bias     | 0.014693 | 0.004931 | 0.031681 | 0.057296 | **+0.001434** | improves overall and straight; tiny regression in transient |
| V2  Linear ST, prior C_α          | 0.016529 | 0.007005 | 0.034497 | 0.062343 | −0.001836  | **regression** — see flag below |
| V3  Linear ST, fit C_α            | 0.016635 | 0.007000 | 0.034822 | 0.062659 | −0.000106  | **regression** — see flag below |

Total drop V0→V3: **−0.000508 rad/s** (i.e. the ladder ends worse than it started). Sum of marginals: −0.000508. Reconciliation error: 0.0%.

V3 fit info: `C_αf = 150000`, `C_αr = 150000`, pegged = False. (The skill-prescribed L-BFGS-B start `[1.5e5, 1.5e5]` did not move — flat-gradient region. A global differential-evolution sanity check converges to `(C_αf, C_αr) ≈ (2.92e5, 2.82e5)` with overall RMSE = 0.016277 — still worse than V0/V1. The skill's V3 step under-performs the prior even when the optimizer is replaced.)

## Attribution

- **V1 is the only improvement.** Marginal drop +1.43e-3 rad/s overall. The improvement is concentrated almost entirely in the *straight* regime (RMSE drops 0.00877 → 0.00493, Δ = −3.84e-3). That is exactly what a per-segment yaw-gyro bias removal is supposed to do: it cancels constant gyro offsets that dominate straight-line residual. Cornering regimes are essentially unchanged.
- **V2 regresses everywhere except straight.** Switching from `tan(δ)` to the steady-state linear-bicycle gain inflates RMSE in steady (+2.76e-3) and transient (+5.55e-3). Cause: the linear-bicycle model assumes small-angle tyres at constant longitudinal speed; the Mach-E segments include moderate-to-large `δ_road` with non-trivial `dδ/dt`, where the linear-ST gain *under-predicts* `ψ̇`. Also V2 drops the per-segment bias that V1 had been crediting — so the straight-line improvement partially survives but is smaller than V1's.
- **V3 is a non-fit.** The L-BFGS-B optimizer the skill prescribes starts at `(1.5e5, 1.5e5)` and never leaves; the loss surface is locally flat at that point with the bounds given. Even a global DE replacement only recovers ≈0.016277 — still worse than V0. V3's marginal is essentially noise (−1e-4).

### Regime contrast (sibling skill `regime-comparison`)

| variant | Δ straight | Δ steady | Δ transient | dominant regime |
|---------|------------|----------|-------------|-----------------|
| V1 | −0.003837 | −0.000051 | +0.000500 | straight |
| V2 | −0.001762 | +0.002764 | +0.005546 | transient |
| V3 | −0.001767 | +0.003089 | +0.005863 | transient |

(Sign convention: negative = RMSE improved relative to V0; positive = regression. Same `regime` column as the parent table, so the numbers reconcile.)

## Regression flags

1. **V2 (Linear ST prior) — regression in steady & transient.** Physical cause: small-angle linearisation + steady-state assumption. Real Mach-E cornering data violates both; `tan(δ)` (V1) actually fits better than `δ/(1+K_us v²)` here.
2. **V3 (Linear ST fit) — regression vs V0 and V1.** Cause is twofold: (i) the prescribed L-BFGS-B initialisation lies in a flat region of the loss surface, so the "fit" returns its starting point; (ii) even with a global optimizer, the best Linear ST RMSE (0.01628) is still worse than V0 (0.01613) and V1 (0.01469). The functional form, not the parameters, is the limiter.

## Recommendation

Ship **V1** (KS with canonical `L` and per-segment yaw-gyro bias removal). It is the only variant that actually improves on the baseline. Skip V2/V3 on Mach-E data; if a steady-state linear model is wanted in future, fit it as a *correction* to KS rather than a replacement, and replace L-BFGS-B with a global optimizer for the C_α fit.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleE-m3-agent-02",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-3/agent-02/REPORT.md",
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
