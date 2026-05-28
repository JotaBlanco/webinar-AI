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

- agent_id: **angleB-m2-agent-04**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-2/agent-04/REPORT.md`

```markdown
# Module-2 / agent-04 (angle-B) — Lateral fidelity report

## Headline
**Lateral yaw-rate RMSE on FORD_MUSTANG_MACH_E_MK1 cut from 0.01613 rad/s → 0.01388 rad/s (-14.0%)** with two interpretable, physics-motivated post-corrections. A third (speed-dependent understeer) regressed and is reported honestly.

## Setup
- **Platform:** `FORD_MUSTANG_MACH_E_MK1` — 315 segments, 913 626 samples @ 50 Hz.
- **Truth column:** `yaw_rate_meas_rads` — measured from the Ford CAN IMU via `opendbc/ford_lincoln_base_pt` (not predicted, not self-consistency).
- **Contract:** `v` and `δ` clamped to measured. Only `ψ̇` (and `a_y`) are predicted. Contract not touched.
- **Regime mask:**
  - straight   : `|ψ̇_meas| < 0.05` rad/s → 816 709 rows
  - steady     : `|ψ̇_meas| ≥ 0.05` and `|δ̇| < 0.05` rad/s → 78 420 rows
  - transient  : `|ψ̇_meas| ≥ 0.05` and `|δ̇| ≥ 0.05` rad/s → 18 497 rows
- **Attribution:** strict marginal V0→V_last; sum = total by construction.

## Variant ladder

| Variant | Description | RMSE all | straight | steady | transient | Marginal Δ (all) |
|---|---|---:|---:|---:|---:|---:|
| V0 | Baseline KS, pred as-is | 0.01613 | 0.00859 | 0.03720 | 0.06099 | — |
| V1 | + per-segment yaw-rate bias removal (estimated on straight regime, applied everywhere) | 0.01461 | 0.00473 | 0.03704 | 0.06117 | -0.00151 |
| V2 | + global constant understeer/overcorrection gain `K* = 1.0903` on cornering | 0.01388 | 0.00560 | 0.03537 | 0.05318 | -0.00073 |
| V3 (regression) | + speed-dependent factor `1/(1 + K_us · v²)`, `K_us = 1.12e-4` | 0.01439 | 0.00411 | 0.03658 | 0.06170 | +0.00051 |

**Total V0 → V2 drop: 0.00224 rad/s (14.0%)**, of which 67% is per-segment bias (V1) and 33% is the gain term (V2).

## Physical interpretation

- **V1 bias** collapses straight-line residual by 45%. Mechanism: IMU mounting / wheel-alignment offset + small CAN-signal zero-error. Per-segment, not global — consistent with device-mount variability between routes.
- **V2 gain `K* = 1.09` (> 1)** means KS *underpredicts* cornering yaw rate by ~9% on average. **Not** the textbook "KS ignores slip" story (which would predict overprediction). It's consistent with drivers overcorrecting steering to compensate for tyre slip — the *measured* `δ` already includes that compensation, so `(v/L)·tan(δ)` carries a small extra factor under the clamp. Largest win on transient: -13%.
- **V3 speed dependence regressed** — gain mismatch is dominated by handling/driver style, not by `v²` understeer growth. Honest negative result.

## Painful absence

Measured **sideslip β** is missing — only computable via a kinematic-vs-GPS heading reconstruction (out of scope here). Would separate "model has no slip" from "driver overcorrects".

## Rule-prevented near-misses

- Almost reported V0 with a global bias subtraction — trap #9 (preprocessing belongs in V1+, not V0).
- Almost used Tesla because its segment count is 3× Ford — trap #1/#7 (Tesla has no truth).
- Almost "improved" by unclamping `δ` — trap #2 (would break contract).
- Almost used `delta_wheel_deg` in a quick check — trap #3, ~17× error.

## Most surprising

**`K* = 1.09 > 1`.** With `δ` clamped to measured, the textbook KS-overprediction story inverts: drivers' steering already contains slip-compensation, so the model **underpredicts** by ~9% in steady cornering. That inverts the standard "ST upgrade closes the gap" story for this contract.

Files: `out/analyze.py`, `out/summary.json`.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleB-m2-agent-04",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-2/agent-04/REPORT.md",
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
