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

- agent_id: **angleE-m4-agent-02**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-4/agent-02/REPORT.md`

```markdown
# REPORT.md — webinar-angle-E / module-4 / agent-02

## Platform
`FORD_MUSTANG_MACH_E_MK1` (SKILL default; 315 segments; 913,626 rows; cleanest of the two Ford platforms with measured truth).

## Operating contract
- `yaw_rate_meas_rads` is measured truth (gyro).
- `v_mps` and `delta_road_rad` are clamped to measured inputs (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`).
- Speed-state agreement is zero by construction; the only metric is `RMSE(yaw_rate_resid_rads)`.

## Variant ladder (strict-marginal accounting, fixed order V0 → V3)

| Variant | Overall RMSE (rad/s) | straight | steady | transient | Marginal Δ overall | Attribution |
|---|---|---|---|---|---|---|
| V0 baseline (as-is residual) | 0.01613 | 0.00877 | 0.03173 | 0.05680 | — | — |
| V1 KS recalibrated (bias-subtracted) | 0.01469 | 0.00493 | 0.03168 | 0.05730 | **−0.00143** | **+100%** (sole gain) |
| V2 Linear ST, prior C_α | 0.01653 | 0.00701 | 0.03450 | 0.06234 | +0.00184 | **regression** |
| V3 Linear ST, fitted C_α | 0.01663 | 0.00700 | 0.03482 | 0.06266 | +0.00011 | **regression** |

Total drop V0 → V3: **−0.000508 rad/s** (the ladder net-regresses). Sum of marginals matches total drop exactly (accounting is consistent; the 15% tolerance is degenerate when total is negative).

## Wins
- **V1 cuts straight-regime RMSE almost in half** (0.00877 → 0.00493). Per-segment gyro-bias subtraction on straight samples is doing real work — there is a measurable per-segment yaw-gyro offset in this dataset.

## Regression flags (per SKILL: "honest regression flags")
- **V2 worsens every regime vs V1 and vs V0.** Physical reason: openpilot's canonical priors `C_αf = 286,551`, `C_αr = 355,912` N/rad produce a `K_us` that under-rotates the model relative to truth on cornering samples. The ST prior is stiffer than the Mach-E's actual cornering compliance on this segment set.
- **V3 worsens further (marginally) vs V2.** Fit returned `C_αf = C_αr = 150,000` N/rad — **exactly the L-BFGS-B initial guess** — with `pegged=False`. This is *not* the SKILL's anticipated bound-pegging failure; the optimizer stalled on the init, suggesting a flat or non-convex loss surface (likely dominated by the v < 2 m/s KS-fallback region). V3's RMSE is essentially "ST evaluated at the init point."

## Attribution
Strict marginal, fixed-order V0→V1→V2→V3. V1 contributes the entire (negative) net drop; V2 and V3 are regressions. The "additivity to within 15%" check is satisfied trivially because marginals sum to total exactly.

## Phase-attribution (RPI evidence)
- **Phase 1 (Research)** surfaced the transient-regime degeneracy (18 rows for Mach-E) — preventing me from over-weighting transient stats in attribution.
- **Phase 1** also flagged that the straight-regime residual is ~5× smaller than steady — pre-committed me to expect V1 (bias-subtraction) to win on straights, which it did.
- **Phase 2 (Plan-lock)** committed me to running V2/V3 even though Phase-1 stats hinted that bias-fix alone explained most of the structure. Without the lock, I'd likely have stopped at V1, missed the V3-stuck-at-init finding, and reported false confidence in ST.
- **Phase 3 (Implement)** discovered the L-BFGS-B stall — a failure mode the SKILL doesn't enumerate.

## Plan dissent
The locked plan implicitly assumed positive net drop and a meaningful 15%-of-total attribution. In practice the ladder net-regressed and V3's "fit" was a no-op. If re-planning: I'd add a V1.5 (per-segment gyro bias + KS canonical L only, no ST) and a pre-fit gradient probe on V3's loss landscape before trusting `minimize`'s convergence flag. The headline deliverable for the original task ("make lateral predictions better, and tell me how much each change contributed") is: **V1 alone, −8.9% overall RMSE, −44% straight-regime RMSE. V2 and V3 should not ship.**

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleE-m4-agent-02",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-4/agent-02/REPORT.md",
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
