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

- agent_id: **angleE-m3-agent-05**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-3/agent-05/REPORT.md`

```markdown
# REPORT.md — webinar-angle-E / module-3 / agent-05

## Platform & contract

- Platform: **FORD_MUSTANG_MACH_E_MK1**
- Truth channel: `yaw_rate_meas_rads` (measured), with `v` and `δ_road` **clamped to measured** (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Speed/steering state agreement is zero by construction; the only metric is the lateral residual `yaw_rate_pred_rads − yaw_rate_meas_rads`.
- Corpus: 913 626 samples across 315 `sim.csv` files (regime split: 785 093 straight / 106 978 steady / 21 555 transient).
- Skill used: `yaw-divergence-triage` (V0 → V1 → V2 → V3 ladder) composed with `regime-comparison` for per-regime attribution.

## Headline

**V1 (KS recalibrated with per-segment straight-line gyro-bias subtraction) is the only change that improves lateral fidelity.** Overall RMSE drops from **0.01613 → 0.01469 rad/s** (−8.9 %). V2 and V3 both regress — physically, they push toward more understeer than these tyres actually have, and the static linear single-track gain has no way to express the transient-cornering structure that dominates the remaining error.

## Variant ladder (RMSE of `ψ̇_pred − ψ̇_meas`, rad/s)

| variant | overall | straight | steady   | transient | marginal Δoverall | attribution | flag |
|---------|---------|----------|----------|-----------|--------------------|-------------|------|
| V0 (CSV residual as-is)                | 0.01613 | 0.00877 | 0.03173 | 0.05680 | —          | baseline                          |   |
| V1 (KS, canonical L, segment gyro-bias) | 0.01469 | 0.00493 | 0.03168 | 0.05730 | **−0.00143** | **gyro-bias correction on straights** | small uptick on transient (+0.0005) |
| V2 (Linear ST, prior C_α)              | 0.01653 | 0.00701 | 0.03450 | 0.06234 | **+0.00184** | ST understeer overshoot           | **REGRESSION** vs V1 on all 3 regimes |
| V3 (Linear ST, fitted C_α)             | 0.01664 | 0.00700 | 0.03482 | 0.06266 | **+0.00011** | optimizer cannot move (see Surprise) | **REGRESSION** vs V1; effectively pegged |

Attribution scheme: strict marginal, fixed order V0→V1→V2→V3, marginal = `RMSE(V_{i-1}) − RMSE(V_i)`. Marginals sum to −0.000508; total drop V0→V3 = −0.000508; reconciliation = 1.0000 (well inside the 15 % tolerance).

## Per-regime contrast vs V0 (sibling skill `regime-comparison`)

| variant | Δ straight | Δ steady  | Δ transient | dominant regime |
|---------|------------|-----------|-------------|------------------|
| V1      | **−0.00384** | −0.00005 | +0.00050    | straight         |
| V2      | −0.00176     | +0.00276 | +0.00555    | transient        |
| V3      | −0.00177     | +0.00309 | +0.00586    | transient        |

The dominant-regime column localises every variant's effect: V1's win is **all in straights** (a gyro-bias removal, not a tyre-model improvement). V2 and V3 each cost the most in **transient** — the regime where the static-gain ST formulation has no degrees of freedom (no `I_z`, no yaw-lag time constant, no slip-angle dynamics).

## Honest regression flags

- **V2 worse than V1 on every regime.** Cause: `K_us` from openpilot's prior `(C_αf=286 551, C_αr=355 912 N/rad)` shrinks the steady-state yaw-rate gain `v·δ / (L·(1+K_us·v²))`. Measured yaw is closer to the kinematic value than to the prior-ST value, so the understeer term over-corrects.
- **V3 worse than V2 and V1.** Cause: the L-BFGS-B fit does not move from its initial value at default `eps`. A 5-seed multi-start (1.5e5,1.5e5 / 5e4,5e4 / 5e5,5e5 / 2.8e5,3.5e5 / 1e5,3e5) returns each seed unchanged. Loss is monotone-decreasing toward the upper bound; best is `(5e5, 5e5)` at 0.01632 — i.e. **the fit is asking for `K_us → 0`, which is just KS.** ST is structurally the wrong family here, not under-tuned. The skill's `pegged` flag is upper-bound-only and so reports `pegged=False`, but functionally V3 is pegged high.

## What's still painful (would unblock the transient column)

- No timestamp-aligned **lateral-acceleration channel** in `sim.csv`, so no way to estimate bank/grade and subtract a road-induced gyro contribution from `yaw_rate_meas_rads` in cornering.
- No **dynamic** ST (yaw-rate state with `I_z` and a yaw-lag time constant) — the static gain has no mechanism for the transient lag responsible for the 0.057 rad/s transient floor.
- No per-segment fit (one global `C_α` pair across 315 segments hides tyre/load variation).

## Variant deltas — concise

- **V1 contributes −0.00143 rad/s overall** — the entire usable improvement.
- **V2 contributes +0.00184 rad/s (regression)** — prior-tyre understeer mismatch.
- **V3 contributes +0.00011 rad/s (further regression)** — degenerate fit; ST model wrong family.
- **Net V0 → V3: +0.00051 rad/s (regression).** **Recommendation: ship V1, discard V2/V3.**

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleE-m3-agent-05",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-3/agent-05/REPORT.md",
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
