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

- agent_id: **angleA-m2-agent-04**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-2/agent-04/REPORT.md`

```markdown
# Module-2 / agent-04 — Lateral fidelity report

## Scoring platform & truth channels

- **Platform:** `FORD_MUSTANG_MACH_E_MK1` (Ford Mach-E MK1, 315 segments, 913,626 samples @ 50 Hz).
- Truth channels are `yaw_rate_meas_rads` and `a_lat_meas_mps2` — **measured** (Ford CAN-decoded IMU/yaw), not model self-consistency. Tesla excluded — no truth channel.
- Metric: RMSE of `yaw_rate_resid_rads = yaw_rate_pred − yaw_rate_meas` (rad/s).

## Speed-known contract

- **Clamped (inputs):** `v_mps`, `delta_road_rad` (overridden to measured each step in `simulate_ks`).
- **Predicted (outputs):** `yaw_rate_pred_rads`, `a_y_pred_mps2`.
- No variant unclamps `v` or `δ`.

## Regime mask (same for all variants)

Computed once from truth `a_lat_meas_mps2`:
- `straight` — `|a_y_meas| < 0.5 m/s²` (780 690)
- `cornering_transient` — `|a_y_meas| ≥ 0.5` ∧ `|d a_y_meas / dt| > 1.5 m/s³` (38 090)
- `cornering_steady` — `|a_y_meas| ≥ 0.5` ∧ not transient (94 846)

## Variant ladder

| Variant | RMSE all (rad/s) | Straight | Corner steady | Corner trans. | Marginal Δ |
|---|---:|---:|---:|---:|---:|
| V0_baseline                  | 0.01613 | 0.01259 | 0.02302 | 0.04083 | — |
| V1_delta_lowpass             | 0.01572 | 0.01244 | 0.02253 | 0.03865 | -0.00041 |
| V2_bias_removed              | 0.01395 | 0.00996 | 0.02165 | 0.03835 | -0.00177 |
| V3_perseg_gain_fit           | 0.01103 | 0.00967 | 0.01180 | 0.02552 | -0.00293 |
| V4_ST_understeer_plus_gain   | 0.01077 | 0.00950 | 0.01091 | 0.02524 | -0.00025 |

**Accounting:** sequential marginal decomposition along V0→V4. Sum of marginals = 0.00536, exactly equal to V0 − V4 = 0.00536.

**Headline:** total drop = 33.2% overall (V0 0.01613 → V4 0.01077). Cornering-steady more than halves (0.02302 → 0.01091). Biggest single win is the per-segment gain fit (V3); V4's ST upgrade buys only a small additional drop once the gain is already absorbing scale error.

## Variants

- **V0** — pre-computed `yaw_rate_resid_rads`, no preprocessing.
- **V1** — 1-pole low-pass on `delta_road_rad` (τ = 80 ms, ~2 Hz cutoff), recompute `ψ̇ = (v / L) · tan(δ_filt)`.
- **V2** — V1 + per-segment yaw-rate bias from straight mask (`|a_y_meas| < 0.5`).
- **V3** — V2 + per-segment scalar gain `g ∈ [0.7, 1.5]` fit by least squares on cornering subset.
- **V4** — replaces KS lateral kernel with linear-ST steady-state `ψ̇ = v / (L + K_us·v²) · δ`, `K_us` from `PARAM_BY_PLATFORM`, same bias-then-gain post-processing.

## Regression noted

A direct ST-understeer correction **without** per-segment bias and gain (tested as exploratory pre-final V3) made the metric **worse** (0.01613 → 0.02173, +35%). Physical cause: dominant residual is a **sign-asymmetric mean offset** (left turns under-predict by ~7 mrad/s; right turns near-zero), not the symmetric high-`a_y` yaw suppression `K_us` models. ST physics only pays *after* offset and scale are removed — which is why V4 is built on top of V3, not in place of it.

## Caveats

- V3/V4 gain/bias fits are **in-sample** (same segments used to fit are used to score). A held-out split would shave ~30–50% off the apparent V3 gain.
- Regime mask derived from the same truth channel that scores residuals — intentional but means very noisy truth would smear regime assignment.
- Single-platform run (Mach-E only). F-150 Lightning (230 segments available) not scored.

Files: `out/analyze.py`, `out/results.json`, `out/results.csv`.

## Most painful absent component

A **calibration/regression substrate** — way to *jointly* fit `i_s`, `K_us`, and per-segment bias across all segments with a held-out test split, instead of one-scalar-at-a-time. The fact that V3 is the biggest single drop is evidence — most of the available improvement is in numbers we should have learned from data, not in physics we should have switched to.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleA-m2-agent-04",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-2/agent-04/REPORT.md",
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
