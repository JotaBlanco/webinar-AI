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

- agent_id: **angleC-m2-agent-04**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-2/agent-04/REPORT.md`

```markdown
# Module-2 / agent-04 (angle-C) — Lateral fidelity ladder (FORD_MUSTANG_MACH_E_MK1)

**Platform scored:** `FORD_MUSTANG_MACH_E_MK1` (315 segments, 913 626 samples @ 50 Hz). `yaw_rate_meas_rads` is **measured truth** from the rlog (Ford CAN decode; Tesla excluded per ratchet rule 4).

**Operating contract (rule 5):** `clamp_v_to_measured=True, clamp_delta_to_measured=True`. Only lateral states are predicted; speed-state agreement is zero by construction. `a_y_pred = v·ψ̇` is coupled (rule 9) but we score on `ψ̇` directly.

**Sign convention:** `residual = pred − meas` (rule 1). Sanity check: `corr(δ_road, ψ̇_meas | cornering) = +0.801` — ISO 8855 consistent (rule 2).

**Regime masks** (fixed across all variants, rule 11):
- straight: `|ψ̇_meas|<0.02 rad/s` and `v>3 m/s` (611 929 samples)
- transient cornering: `|ψ̇_meas|>0.05` and `|dψ̇/dt|>0.15 rad/s²` (17 400)
- steady cornering: `|ψ̇_meas|>0.05` and not transient (79 458)

**Train/test:** interleaved every-5th-sample split (rule 7). All RMSE below is held-out test.

## Variant ladder (RMSE in deg/s; strict marginal accounting V0 → V_last)

| # | Variant | All | Straight | Steady | Transient | Δ vs prev | Fit scope |
|---|---|---|---|---|---|---|---|
| V0 | baseline `yaw_rate_resid_rads` as-is | 1.013 | 0.487 | 2.312 | 3.012 | — | n/a |
| V1 | global bias removal (b=+0.093 deg/s) | 1.015 | 0.484 | 2.321 | 3.024 | **+0.2% (regression)** | per-platform |
| V2 | affine gain+bias on `ψ̇_pred` (α=1.0795, β=-0.037 deg/s) | 0.964 | 0.517 | 2.194 | 2.549 | -5.0% | per-platform |
| V3 | + per-segment lag align (k=+3 samples = **60 ms**, pred leads meas) | 0.949 | 0.510 | 2.186 | 2.397 | -1.5% | per-platform |
| V4 | + per-segment median-bias subtraction | 0.848 | 0.230 | 2.180 | 2.398 | -10.7% | **per-segment (CALIBRATION, rule 8)** |

**Net model-only improvement (V0 → V3, no calibration):** -6.3% all-regime, **-20% in transients**.
**With per-segment calibration (V0 → V4):** -16.3% overall, -53% on straight regime (sensor zero offsets).

## Regression flagged (rule)

**V1 ↑0.2%** is a real regression. Physical cause: the global median residual on the train set is non-zero because cornering samples have asymmetric pred-meas error (model under-gains in turns). Subtracting that median pushes straight-line residuals away from zero. V2's affine fit subsumes V1 cleanly, so V1 is dropped from the recommended stack.

## What each change contributed

- **V2 gain α≈1.08 (-5.0%)** — kinematic single-track under-predicts yaw rate at given (v, δ_road) because it ignores tire slip; an 8% gain bump is the standard "missing dynamic bicycle" correction. The only V*model*-improvement worth keeping.
- **V3 lag 60 ms (-1.5% overall, -5.9% transient)** — measurement chain (CAN + IMU) lags KS prediction by ~3 samples; matters only for transients.
- **V4 per-segment bias (-10.7%)** — almost entirely straight-line gyro zero offset (RMSE_straight drops 0.510 → 0.230). **Calibration, not a model improvement** per rule 8.

## Per-regime takeaways

- **Straight:** residual dominated by per-segment gyro zero (V4 halves it). Model is fine.
- **Steady cornering:** dominated by gain error; V2 takes ~5% out, V3/V4 barely move it.
- **Transient:** dominated by lag *and* gain; V2+V3 together cut it by 20%.

## Painful absence

No yaw-rate truth on Tesla (rule 4) — I cannot test whether α=1.08 generalises across the openpilot fleet, only across the two Ford platforms (and I only ran one, time-budget). The improvement is genuinely *per-platform*, not *per-vehicle-class*, until F-150 confirms.

## Near-misses

Started toward a speed-dependent gain α(v) (slip grows with v²); the fit is non-trivially better but the variance increase on the held-out test split argues against it under rule 7 — left for next iteration.

## Surprise

V1 — a textbook "remove the bias first" move — is a **regression** here. The bias is asymmetric (cornering-driven), and V2 absorbs it cleanly with a coefficient that also makes physical sense. The intuition "always bias-correct first" is wrong on autocorrelated lateral residuals.

Files: `tools/analyze.py`, `out/variant_ladder.csv`.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleC-m2-agent-04",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-2/agent-04/REPORT.md",
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
