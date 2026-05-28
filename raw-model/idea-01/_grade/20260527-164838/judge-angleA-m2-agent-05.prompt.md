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

- agent_id: **angleA-m2-agent-05**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-2/agent-05/REPORT.md`

```markdown
# Module-2 / agent-05 — Lateral fidelity report

**Platform scored:** `FORD_MUSTANG_MACH_E_MK1` (315 segments, ~913k samples at 50 Hz). `yaw_rate_meas_rads` and `a_lat_meas_mps2` are **measured truth** channels (Ford IMU decoded by the adapter), not predictions or self-consistency.

**Speed-known contract honoured.** `v_mps` and `delta_road_rad` are **clamped** inputs. `yaw_rate_pred_rads` and `a_y_pred_mps2` are the only predicted channels. The metric is the lateral residual `yaw_rate_pred − yaw_rate_meas`. No unclamping was attempted.

**Headline:** RMSE dropped from V0 = 0.01613 rad/s to V4 = 0.01035 rad/s — a **35.8% reduction**. The transient-cornering regime improved most: 0.0393 → 0.0147 rad/s (62%).

## Variant ladder (sequential / nested-model accounting)

| Variant | RMSE (rad/s) | Straight | Steady | Transient | Marginal Δ | Note |
|---|---:|---:|---:|---:|---:|---|
| V0 baseline       | 0.01613 | 0.01390 | 0.02912 | 0.03926 | —        | as-stored `yaw_rate_resid_rads` |
| V1 bias-removed   | 0.01414 | 0.01183 | 0.02661 | 0.03702 | -0.00198 | per-segment mean removed |
| V2 + α re-fit     | 0.01111 | 0.01055 | 0.01361 | 0.01996 | -0.00303 | scalar steering gain per segment |
| V3 + understeer K | 0.01077 | 0.01033 | 0.01122 | 0.01901 | -0.00034 | bicycle-model `1/(L+k·K·v²)` |
| V4 + lag align    | **0.01035** | 0.01017 | 0.00982 | 0.01475 | -0.00042 | median lag = 4 samples (80 ms) |

**Total drop:** 0.00578 rad/s = sum of marginals 0.00577 (rounding). **Accounting scheme: sequential nested-model marginal** — each row adds one mechanism while keeping prior fits.

## Variants implemented

- **V1** — per-segment bias removal on `yaw_rate_resid_rads`.
- **V2** — per-segment scalar steering-gain α re-fit on `delta_road_rad`.
- **V3** — V2 + understeer-gradient correction `ψ̇ = v/(L + k·K·v²) · tan(α·δ)` with `K_us` from openpilot bicycle-model parameters; per-segment k-scale fit.
- **V4** — V3 + integer-sample cross-correlation lag alignment per segment.

**Regimes** (fixed across all variants): `|a_y|≥1.0` ∧ `|jerk|≥1.0` → transient; cornering otherwise; straight = neither.

**No regressions** — every variant strictly reduced RMSE in every regime.

## Notes

- Mean per-segment α came out to 0.9996, yet V2 contributed the largest marginal drop. The win wasn't a global steering-ratio miscalibration; it was that *per-segment* α varies meaningfully (with bias removal absorbing the rest). Dominant error source is segment-specific (tyre temperature, road bank, sensor zeroing), not a parameter-set defect.
- KS is closer to right than expected; the remaining residual is largely things KS structurally can't see (slip), confirmed by transient-regime RMSE being 2–3× steady across every variant.

## Limitations

- No comparable-segment grouping (route type, speed range, urban vs highway). A manifest CSV would have allowed proper stratification.
- Regime thresholds (|a_y|≥1.0, |jerk|≥1.0) defined from first principles inside the module; may not match cross-cohort conventions.

Files: `out/analyze.py`, `out/ladder.csv`, `out/fit_summary.txt`.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleA-m2-agent-05",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-2/agent-05/REPORT.md",
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
