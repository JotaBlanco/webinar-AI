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

- agent_id: **angleA-m3-agent-03**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-3/agent-03/REPORT.md`

```markdown
# Module-3 / agent-03 — Lateral fidelity variant ladder (Mach-E)

## Scope and contract

- Platform: **FORD_MUSTANG_MACH_E_MK1** (315 segments, 913 626 rows at 50 Hz).
- `yaw_rate_meas_rads` is the **measured** Ford CAN/IMU truth channel — not a prediction, not a self-consistency replay.
- Under the speed-known lateral-only contract, `v_mps` and `delta_road_rad` are **clamped** to measurement at every integrator step; the **predicted** quantity under test is `yaw_rate_pred_rads`.
- Residual scored: `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads`.
- Regime mask (held constant): straight `|δ|<0.01`, steady `|δ|≥0.01 ∧ |dδ/dt|<0.05`, transient `|δ|≥0.01 ∧ |dδ/dt|≥0.05`. Counts: 785 093 / 106 978 / 21 555.
- Sign sanity: `corr(δ, ψ̇_meas) = +0.690` — left-positive convention confirmed.

## Variant ladder (yaw-rate RMSE in rad/s)

| Variant | Description | Overall | Straight | Steady | Transient | Marginal Δ overall |
|---|---|---:|---:|---:|---:|---:|
| V0 | Stock `yaw_rate_resid_rads` as-is                                                       | 0.01613 | 0.00877 | 0.03173 | 0.05680 | — |
| V1 | KS recalibrated (canonical L) + per-segment yaw-gyro bias on straights                  | 0.01469 | 0.00493 | 0.03168 | 0.05730 | **-0.00144** |
| V2 | Linear ST steady-state with prior `C_α` (286.6k / 355.9k)                                | 0.01551 | 0.00339 | 0.03430 | 0.06277 | **+0.00082** (regression) |
| V3 | Linear ST with fit `C_α` (L-BFGS-B + DE cross-check; best ≈ 362k / 369k)                | 0.01564 | 0.00349 | 0.03462 | 0.06307 | **+0.00013** (regression) |
| V4 | Ridge residual learner on `[v, |a_y|, |δ|, sign(δ̇)]`, LOO OOF                           | 0.01541 | 0.00357 | 0.03414 | 0.06179 | **-0.00023** |

## Attribution

- **Strict marginal**, fixed order V0→V1→V2→V3→V4. Sum of marginals: `-0.00144 + 0.00082 + 0.00013 - 0.00023 = -0.00072`. Total V0→V4: `0.01613 - 0.01541 = 0.00072`. **Match exact** (<1% of total drop, well under 15% guard).

## What actually moved the needle

- **V1 carries the whole improvement.** Stock `yaw_rate_pred_rads` already uses canonical `L = 2.984 m` (max recompute diff = 3e-6 rad/s) — there is no L-error to fix. V1's lift is entirely **per-segment yaw-gyro bias subtraction**: 311 of 315 segments had ≥5 straight samples; bias mean 0.0007 rad/s, std 0.0070 rad/s, range [-0.024, +0.019]. Removing those static offsets cuts the straight-regime RMSE almost in half (0.00877 → 0.00493).
- **Steady and transient regimes barely move under V1**, because gyro bias is a constant offset and the steady/transient residuals are dominated by un-modelled slip, not bias.
- **V2 and V3 are regressions.** Physical cause: openpilot's prior cornering stiffnesses (286.6k front / 355.9k rear) characterise a stiffer-than-reality tyre, so `K_us` magnitude is too small (slight oversteer/near-neutral) — at moderate `v` the ST yaw-rate gain ends up *larger* than reality, overshooting `ψ̇_meas`. The DE fit (which dodges the L-BFGS-B local-minimum trap at x0) settles at ≈ (362k, 369k) — even higher Cα than the prior — confirming the loss surface wants *more* stiffness, i.e. closing the wrong gap. The actual gap is non-linear slip and tyre relaxation length, which a linear ST cannot represent.
- **V4 (residual learner LOO) recovers most of V3's regression** but cannot beat V1. With OOF RMSE 0.01541, the learner finds modest structure in `[v, |a_y|, |δ|, sign(δ̇)]` against the V3 residual, but it's repairing damage V2/V3 caused. **Honest finish is to ship V1.**

## Headline result

- Best lateral yaw-rate RMSE: **V1 = 0.01469 rad/s** (vs V0 = 0.01613 rad/s, an **8.9% reduction**).
- All of that gain is attributable to **per-segment yaw-gyro bias subtraction**, computed from straight-line samples only.
- The ladder is honest about V2/V3 being regressions.

## Limitations

- The `a_y` channel used in the residual learner is `a_y_pred_mps2` (predicted), not `a_lat_meas_mps2`. Using the measured channel might add genuine slip-onset information; unexplored.
- Bias subtraction is per-segment; a device-level bias estimator would generalise better but was out of scope.
- No non-linear or dynamic ST (Pacejka, relaxation length) — references explicitly bound the ladder to KS → linear-ST → residual learner.

Files: `out/ladder_summary.json`, `tools/run_ladder.py`.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleA-m3-agent-03",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-3/agent-03/REPORT.md",
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
