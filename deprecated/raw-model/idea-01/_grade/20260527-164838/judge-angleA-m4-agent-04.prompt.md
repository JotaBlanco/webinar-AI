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

- agent_id: **angleA-m4-agent-04**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-4/agent-04/REPORT.md`

```markdown
# Module-4 / agent-04 — Lateral-fidelity variant ladder (Ford Mustang Mach-E)

## Setup

- **Platform:** `FORD_MUSTANG_MACH_E_MK1`. Lateral-truth channel is `yaw_rate_meas_rads`, the **measured** yaw rate decoded from the rlog IMU (not predicted, not the KS integrator state).
- **Speed-known contract.** All Ford `sim.csv` rows were produced with `clamp_v_to_measured=True` and `clamp_delta_to_measured=True`, so `v_mps` and `delta_road_rad` are **clamped** inputs and `yaw_rate_pred_rads` is the resulting **predicted** lateral output. The scored quantity is `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads`.
- **Cohort:** 60 Mach-E sim segments (first 60 by lexicographic path order). Same segment set and same regime mask are **held constant across every row** in the variant ladder.
- **Regime mask** (same definition for every variant): `straight = |δ_road| < 0.01 rad`; `steady = |δ_road| ≥ 0.01 rad ∧ |dδ/dt| < 0.05 rad/s`; `transient = |δ_road| ≥ 0.01 rad ∧ |dδ/dt| ≥ 0.05 rad/s`.
- **Attribution scheme:** strict marginal in the fixed order V0→V1→V2→V3→V4. Marginal drop on row i = `RMSE(V_{i−1}) − RMSE(V_i)`.

## Variant ladder

| Variant | Overall RMSE (rad/s) | Straight | Steady | Transient | Marginal Δ (rad/s) |
|---------|----------------------|----------|--------|-----------|--------------------|
| V0 — baseline `yaw_rate_resid_rads` as-is                                                              | 0.01214 | 0.00851 | 0.02519 | 0.04889 | — |
| V1 — KS recalibrated (canonical L=2.984 m) + per-segment yaw-gyro bias on straights                    | 0.01055 | 0.00506 | 0.02602 | 0.05116 | -0.00159 |
| V2 — Linear ST with openpilot prior Cα (Cf=286 551, Cr=355 912 N/rad)                                  | 0.01248 | 0.00335 | 0.03424 | 0.06362 | +0.00193 |
| V3 — Linear ST with fit Cα (Cf=Cr≈150 000 N/rad, interior optimum)                                     | 0.01260 | 0.00343 | 0.03458 | 0.06398 | +0.00012 |
| V4 — Ridge residual learner on V3, LOSO CV                                                             | 0.01005 | 0.00351 | 0.02544 | 0.05382 | -0.00255 |

Total drop V0 → V4: **0.00210 rad/s** (17.3% reduction). Sum of marginal drops: 0.00210 rad/s. Coherence error `|Σmarg − total|/|total| = 0.00 < 0.15`.

## What each variant did

- **V1 (positive, -0.00159).** Pulled `L` from `PARAM_BY_PLATFORM` (2.984 m) and subtracted per-segment mean yaw-gyro bias on straights (60/60 segments had ≥10 straight samples). Mean bias ≈ 0.0002 rad/s — small but enough to halve the straight-line RMSE (0.0085 → 0.0051).
- **V2 (regression, +0.00193).** Switched to the linear single-track steady-state yaw-rate gain `ψ̇ = v·δ / (L·(1 + K_us·v²))` with openpilot's prior cornering stiffnesses. **Worsened steady and transient cornering** (the regimes ST is supposed to help). See below.
- **V3 (regression, +0.00012).** Re-fit `(Cf, Cr)` in `(5e4, 5e5) N/rad` bounds; the optimiser landed at an **interior** point `Cf=Cr=150 000` rather than pegging the upper bound, but the resulting RMSE is *still* worse than V1.
- **V4 (positive, -0.00255).** Ridge regression (α=1.0) on `[v, |a_y|, |δ|, sign(δ̇)]` against V3 residuals, **leave-one-segment-out** CV. Recovers everything V2/V3 lost, plus more.

## Regression analysis

V2 and V3 both increased overall RMSE relative to V1. The references material predicted this pattern: openpilot's `Cα` prior is stiffer than the Mach-E tyres want, so the steady-state ST gain over-attenuates yaw at speed. The residual structure left after V1 is non-linear (slip-angle saturation), which a linear-ST steady-state model cannot represent regardless of the `(Cf, Cr)` you pick. V3's fit confirmed this: it walked stiffnesses down to an interior optimum and **still** could not beat V1. Physical cause: residuals at high lateral acceleration aren't a stiffness mismatch; they're a missing slip-angle dynamics term. A model-form gap, not a parameter gap.

## What V4 actually learned

LOSO Ridge picks up regime-dependent residual: with `|a_y|` and `|δ|` features it's roughly learning the slip-angle gain that linear ST omits. Because LOSO holds out a full segment for every prediction, 0.01005 is genuine out-of-fold. V4 beats V1 by 0.00050 rad/s overall, win concentrated in steady cornering (transient is slightly worse than V1 in absolute terms, 0.05382 vs 0.05116; the net win is in steady and overall).

## Limitations

- 60-segment subsample (first by path-order), not the full 315 — picked for budget.
- Lightning platform not run.
- V4 model intentionally tiny (4 features, Ridge α=1.0).

## What the absence of a shared baseline cost me

This module includes the skill, references, and eval, but no `_shared` reference cohort. I cannot externally verify whether 17.3% reduction is "what a clean run looks like". The eval is structural (shape, attribution accounting, regression honesty), not numerical (is your RMSE near canonical). Shape-correctness and self-consistency only.

Files: `out/run_ladder.py`, `out/ladder.json`.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleA-m4-agent-04",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-4/agent-04/REPORT.md",
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
