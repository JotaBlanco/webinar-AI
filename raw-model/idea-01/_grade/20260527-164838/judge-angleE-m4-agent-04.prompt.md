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

- agent_id: **angleE-m4-agent-04**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-4/agent-04/REPORT.md`

```markdown
# REPORT.md — module-4 / agent-04 / webinar-angle-E

## Platform & contract
- Platform: **FORD_MUSTANG_MACH_E_MK1** (315 segments, 913,626 rows @ ~50 Hz).
- Truth: `yaw_rate_meas_rads` (measured). Inputs `v`/`δ` are clamped to measured per the operating contract. Speed-state agreement is zero by construction and is **not** the metric. The metric is `RMSE(yaw_rate_resid_rads)`.

## Variant ladder
Order is fixed V0 → V1 → V2 → V3 per the `yaw-divergence-triage` skill. Per-regime regime mask uses the **skill's `δ`-based mask** (`|δ_road| < 0.01` straight, `|δ| ≥ 0.01 & |δ̇| < 0.05` steady, else transient).

| variant | overall RMSE | straight | steady | transient | marginal vs prior |
|---|---|---|---|---|---|
| V0 — baseline KS (as-shipped) | 0.016127 | 0.008768 | 0.031733 | 0.056797 | — |
| V1 — KS, canonical `L`, per-segment straight-line bias removed | **0.014693** | **0.004931** | 0.031681 | 0.057296 | **+0.001434** |
| V2 — Linear ST, openpilot-canonical `C_αf, C_αr` (prior) | 0.016529 | 0.007005 | 0.034497 | 0.062343 | −0.001836 (regression) |
| V3 — Linear ST, `C_αf, C_αr` fit (L-BFGS-B, bounds 5e4–5e5) | 0.016635 | 0.007000 | 0.034822 | 0.062659 | −0.000106 (regression) |

- Total drop V0 → V3: **−0.00051 rad/s** (V3 is worse than V0).
- Best variant overall: **V1** (Δ vs V0 = 0.001434 rad/s, −8.9% RMSE).
- Marginal-sum accounting reconciles to 1.000× total drop (exact).

## Attribution (regime-comparison sub-table)
Signed Δ RMSE vs V0; negative = improvement.

| variant | Δ straight | Δ steady | Δ transient | dominant regime |
|---|---|---|---|---|
| V1 | **−0.003837** | −0.000051 | +0.000500 | straight |
| V2 | −0.001762 | +0.002764 | +0.005546 | transient |
| V3 | −0.001767 | +0.003089 | +0.005863 | transient |

- V1 earns its entire improvement in **straight** by removing per-segment yaw-gyro bias.
- V2 and V3 trade a small straight-line gain (they inherit some bias cancellation through the steady-state gain reshape) for **substantial** steady and transient regressions — the ST gain `1/(1 + K_us v²)` is *too soft* given the openpilot-canonical `C_α` prior on the Mach-E.

## Regression flags
- **V1 transient: +0.9%** — minor; bias subtraction nudges the transient mean. Not actionable.
- **V2 steady: +8.7%**, **V2 transient: +9.8%** — exceed the 5% threshold. Cause: openpilot ST prior on Mach-E yields `K_us > 0` (understeering); but the as-shipped baseline already absorbs much of that gain implicitly through `tan(δ)` saturation at the speeds in this dataset (most of the data is at low-to-mid v). The "softer" ST steady-state gain under-predicts yaw-rate at moderate `v·δ`.
- **V3 steady: +9.7%**, **V3 transient: +10.3%** — V3 *increased* the regression. The fit returned `C_αf = C_αr = 1.5e5 N/rad`, identical to the L-BFGS-B initial guess: the optimizer did not move (flat/noisy loss surface with finite-difference gradients over 914k rows). **Not pegged at a bound**, but effectively pinned at init.

## Phase-surfacing notes (RPI evidence)
- **Phase 1 (research)** surfaced the data-shape facts: clean residuals (no NaN), big regime-RMSE gap (transient ~6× straight on baseline), Mach-E preferable to Lightning because Lightning has a steering-offset confound. It also flagged the regime-mask choice as an open question.
- **Phase 2 (plan)** committed to Mach-E and to the skill's marginal-vs-prior accounting before any V1/V2/V3 numbers were computed. Locked the rejection of V4 residual learners, nonlinear tire fits, and Lightning.
- **Phase 3 (implement)** revealed two things the plan did not anticipate: (a) V2 *regresses* against V0 in steady and transient, and (b) the V3 fit did not move from init. Both are reported as-is, not papered over.

## Plan dissent
- The Phase-2 plan described V1 as "fit `L_eff` by least-squares on straight + steady samples". The skill helper `triage.v1_ks_recalibrated` instead uses **canonical `L`** plus per-segment **yaw-gyro bias subtraction** on straight-line samples. I followed the skill helper (because the plan also commits to the skill's marginal-vs-prior convention and the workshop's whole point is comparing identical skills under different protocols). The two recipes attack different errors — `L_eff` would have absorbed a steady-state gain error; the skill's recipe absorbs a per-segment sensor bias. Given V1's straight-RMSE collapsed from 0.00877 → 0.00493 (−44%) while steady was untouched, the skill's recipe is clearly attacking the dominant V0 error on this dataset (gyro bias, not gain) — so the deviation is defensible.
- A small parameters-API patch was required: `PARAM_BY_PLATFORM[platform]` returns a frozen dataclass instance but `triage.v1/v2/v3` indexes it like a dict (`P["L"]`). I wrapped the loader with `dataclasses.asdict` at call time; no skill code was modified.
- V3's failed fit (optimizer pinned at init) is a real implementation gap in the skill helper (L-BFGS-B with default `eps` on a 914k-row finite-difference gradient is brittle). I did **not** swap optimizers because the plan locked the helper; instead I reported it as a regression with cause, per the skill's "honest regression flags" rule.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleE-m4-agent-04",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-4/agent-04/REPORT.md",
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
