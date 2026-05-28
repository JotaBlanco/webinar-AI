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

- agent_id: **angleB-m2-agent-03**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-2/agent-03/REPORT.md`

```markdown
# Module-2 / agent-03 (angle-B) — Lateral Fidelity Variant Ladder

**Platform:** `FORD_MUSTANG_MACH_E_MK1` (315 segments, 913,626 samples @ 50 Hz, ~305 min). F-150 Lightning not scored (time budget).

**Truth channel:** `yaw_rate_meas_rads` — measured from the Ford CAN bus via `opendbc/ford_lincoln_base_pt`, decoded by `code/adapter_ford_rlog.py`. Not predicted, not self-consistency, not GPS-derived.

**Operating contract (speed-known, lateral-only):** `clamp_v_to_measured=True`, `clamp_delta_to_measured=True`. **Clamped:** `v`, `δ`. **Predicted:** `ψ̇`, `a_y`, `ψ`, `(x,y)`. Speed-state RMSE zero by construction and not reported.

**Metric:** RMSE of `yaw_rate_resid_rads = ψ̇_pred − ψ̇_meas`, broken out by regime, in **mrad/s**.

**Regime mask** (consistent across all variants):
- straight: `|ψ̇_meas| < 0.02 rad/s` — 78.6% of samples
- transient_corner: not straight ∧ `|dψ̇/dt| > 0.15 rad/s²` — 2.3%
- steady_corner: remainder — 19.1%

## Ladder

| Variant | Description | Overall | Straight | Steady | Transient | Marginal |
|---|---|---:|---:|---:|---:|---:|
| V0 | KS baseline, `yaw_rate_resid_rads` as-is | 16.127 | 7.990 | 28.252 | 50.145 | — |
| V1 | + per-segment yaw-rate bias removal | 14.143 | 4.967 | 26.129 | 46.893 | -1.984 |
| V2 | + replace `(v/L)·tan(δ)` with linear ST `v·δ/(L·(1+K_us·v²))`, K_us=5.62e-4 s²/m² from shipped Cα | 14.746 | 4.559 | 27.106 | 51.591 | +0.604 **(regression)** |
| V3 | + first-order steering lag, τ=0.08 s (rack/EPS dynamics), grid-fit | 14.316 | 4.368 | 26.765 | 48.234 | -0.430 |
| V4 | + empirical understeer gradient K_us=5.00e-4 s²/m² (was 5.62e-4) | 14.202 | 4.354 | 26.519 | 47.938 | -0.114 |

**Total drop V0 → V4:** 1.924 mrad/s (11.9%). **Sum of marginal drops:** 1.924 mrad/s. Cumulative/marginal accounting; each variant evaluated with all previous applied.

## Regression: V2 worsened the metric on its own

The linear ST steady-state gain at the **shipped Cα prior** under-rotates the model relative to KS (because `K_us > 0` cuts gain at speed). Straight RMSE improved (4.967→4.559) but steady and transient regressed. The shipped Cα ratio is dominated by `l_r·Cr − l_f·Cf` and the resulting `K_us=5.62e-4` is essentially noise-band — close to neutral steer. Physical cause: production Cα prior is calibrated for openpilot's lat planner, not for residual minimisation; small K_us mismatch is amplified in cornering. The regression is closed by combining with V3 (lag) and V4 (fit Cα-equivalent K_us).

## What remains unexplained

Even at V4 the transient-cornering RMSE is **47.9 mrad/s** — 3.4× the straight-line floor. This is the residual the KS contract cannot close. It is the slip-angle / tyre-lag / weight-transfer signature that an ST dynamic model with proper tyre relaxation length would address.

## Variants tried but not promoted

- Global `δ` zero-offset calibration: best offset +0.5 mrad, drop ≈ 0.017 mrad/s — below the discretisation step.

## Reply

**Painful absence**: no tyre-slip term, no sideslip state β, no relaxation length. Transient-cornering RMSE stays at 47.9 mrad/s after V4 — 3.4× the straight-line floor.

**Rule-prevented near-misses**: trap #2 (used `delta_road_rad`, never touched clamp_*); trap #3 (deg vs rad); trap #5 (parameters from PARAM_BY_PLATFORM); trap #9 (V0 is raw residual, bias removal lives in V1); trap #10 (marginal attribution, sum=total to <0.01%).

**Most surprising**: ST steady-state gain swap (V2) **regressed** on its own. Shipped Cα prior gives `K_us=5.62e-4 s²/m²` — essentially neutral-steer — under-rotates relative to KS at speed. Empirically fitting K_us only moves it to 5.00e-4. The Cα prior is not the right calibration target for these tyres on these roads (as AGENTS.md warns); but the gap it leaves is small. The real lateral lie is in the **transient regime**, and the slip angle is what KS+ST-linear both ignore in the same way.

Files: `out/analyze.py`, `out/ladder.json`.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleB-m2-agent-03",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-2/agent-03/REPORT.md",
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
