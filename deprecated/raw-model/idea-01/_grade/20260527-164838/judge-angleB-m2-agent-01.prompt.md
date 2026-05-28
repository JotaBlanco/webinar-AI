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

- agent_id: **angleB-m2-agent-01**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-2/agent-01/REPORT.md`

```markdown
# Module-2 / agent-01 (angle-B) — Lateral fidelity variant ladder

## Scope and contract

- **Platforms scored:** `FORD_MUSTANG_MACH_E_MK1` (315 segs) and `FORD_F_150_LIGHTNING_MK1` (230 segs). Tesla excluded — no decoded truth.
- **Truth channel:** `yaw_rate_meas_rads` from the Ford CAN DBC (`opendbc/ford_lincoln_base_pt`). Measured by the chassis IMU/ESC stack, not a model self-consistency check.
- **Speed-known contract:** `v_mps` and `delta_road_rad` are clamped to measurement at every integration step. The predicted channel under test is `yaw_rate_pred_rads`. Residual sign: `pred − meas`.
- **Segment set & regime mask identical across V0..V3.** Regimes: straight (|ψ̇|<0.05 rad/s), steady (cornering, |ψ̈|<0.2 rad/s²), transient (cornering, |ψ̈|≥0.2). Pooled RMSE sample-weighted.

## Variant ladder (cumulative)

| Variant | What changes |
|---|---|
| V0 | Baseline: `yaw_rate_resid_rads` from `sim.csv`, no preprocessing |
| V1 | V0 + per-segment yaw-rate bias removal |
| V2 | V1 + per-segment steering→yaw latency alignment (integer-sample shift, xcorr peak on cornering, ±8 samples = ±160 ms) |
| V3 | V2 + replace KS kinematic gain with ST steady-state gain `ψ̇ = v·δ / (L·(1+K_us·v²))`, K_us from `PARAM_BY_PLATFORM` |

K_us: Mach-E 5.6e-4 s²/m, Lightning 4.5e-4 s²/m (both understeer-positive).

## Results — Ford Mustang Mach-E MK1 (RMSE in mrad/s)

| Variant | straight | steady | transient | all (pooled) | Δ vs prev (all) |
|---|---|---|---|---|---|
| V0 | 9.01 | 27.15 | 44.72 | **13.16** | — |
| V1 | 5.31 | 25.56 | 42.23 | **10.73** | -2.44 (-18.5%) |
| V2 | 5.23 | 25.34 | 38.23 | **10.44** | -0.29 (-2.7%) |
| V3 | 4.27 | 29.67 | 46.25 | **11.57** | +1.14 (+10.9%) **regression** |

Best variant for Mach-E: **V2** (-20.7% vs V0).

## Results — Ford F-150 Lightning MK1 (RMSE in mrad/s)

| Variant | straight | steady | transient | all (pooled) | Δ vs prev (all) |
|---|---|---|---|---|---|
| V0 | 10.25 | 32.92 | 39.80 | **15.84** | — |
| V1 | 8.53 | 30.14 | 38.55 | **14.16** | -1.68 (-10.6%) |
| V2 | 8.45 | 29.92 | 36.48 | **13.95** | -0.21 (-1.5%) |
| V3 | 4.93 | 16.32 | 22.53 | **7.92** | -6.03 (-43.2%) |

Best variant for Lightning: **V3** (-50.0% vs V0). The ST upgrade collapses cornering residual by ~50% on the truck.

## V3 regression on Mach-E — physical cause

The ST steady-state gain de-amplifies KS yaw rate by `1/(1+K_us·v²)`. On the Lightning, KS over-predicts cornering yaw rate (heavier vehicle, longer wheelbase, larger lateral compliance) and the ST correction is in the right direction. On the Mach-E, the KS prediction was already biased *low* on cornering peaks — most of the cornering error is *not* a simple gain error but high-frequency content from suspension/tyre dynamics KS can't see. De-amplifying further with K_us>0 worsens both cornering bins.

## Painful absence

A **shared evaluation module with the regime definitions pinned**. AGENTS.md+CLAUDE.md are 23 KB of conventions re-paid every turn but neither pins regime thresholds or a pooled-RMSE function. Had to invent `|ψ̇|<0.05, |ψ̈|<0.2` — defensible but not blessed. Also had to hand-copy K_us inputs from `code/parameters.py` (symlinked `code/` isn't import-clean).

## Rule-prevented near-misses

- Almost ran a per-platform K_us calibration that would have made V3 win on Mach-E. The prior comes from `carParams` and calibrating-on-the-same-data-we-score-on would be a leak. Held off; flagged as V4-future on a held-out split.

## Most surprising

**Per-segment yaw-rate bias is large, consistent, physical.** Median +1.1 mrad/s on Mach-E, +3.3 mrad/s on Lightning. Real sensor offsets / integration drift. Removing them collapses straight-line RMSE by ~40%. Expected the headline win to come from physics (V3); on Mach-E the cheapest preprocessing dominates. The truck is where the linear-tyre upgrade pays off.

Files: `out/analyse.py`, `out/plot_variants.py`, `out/variant_rmse.png`, `out/per_segment_*.csv`, `out/summary.json`.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleB-m2-agent-01",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-2/agent-01/REPORT.md",
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
