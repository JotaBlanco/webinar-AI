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

- agent_id: **angleD-m4-agent-03**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-4/agent-03/REPORT.md`

```markdown
# REPORT — Lateral fidelity ladder, Mach-E

- **Platform**: `FORD_MUSTANG_MACH_E_MK1` (Mach-E). Mach-E chosen because `yaw_rate_meas_rads` is the **measured** truth channel decoded from the openpilot Ford party DBC (Tesla rlogs do not decode this).
- **Operating contract**: `v` and `δ` are **clamped to measured** under the speed-known, lateral-only contract. Speed-state agreement is zero by construction and is not the metric here. Residuals are reported on `yaw_rate_pred − yaw_rate_meas`.
- **Data**: 8 Mach-E segments, 23,191 rows. Regime distribution: 21,264 straight / 1,559 steady / 368 transient. (Sample is straight-heavy; cornering numbers are noisier than the overall.)
- **Skills used**: composed `regime-segmentation` (load + tag) then `lateral-fidelity-triage` (variant ladder + sensor gate). Regime thresholds: `|δ|<0.01 rad` straight, `|dδ/dt|<0.05 rad/s` for steady vs. transient — identical in both skills.
- **Attribution scheme**: strict marginal, fixed order V0→V1→V2→V3→V4. Per-variant marginal = `RMSE(V_{i-1}) − RMSE(V_i)`. Sum of marginals equals total drop within numerical precision (well under the 15% guardrail).
- **Sensor gate** (`sensor.py out/best_V1.csv`): PASS sign-consistency (`corr(pred,meas)=0.997` on cornering) and PASS regression-check (`RMSE=0.01524 ≤ V0=0.01796`).

| Variant | Overall (mrad/s) | Straight | Steady | Transient | ΔOverall vs V0 |
|---|---:|---:|---:|---:|---:|
| V0  baseline (as-shipped) | 17.96 | 13.31 | 34.94 | 70.23 | +0.0% |
| V1  KS recalibrated + per-segment gyro bias | 15.24 | 7.20 | 37.10 | 76.17 | +15.2% |
| V2  Linear ST, prior C_α (286.6k / 355.9k) | 19.32 | 9.69 | 48.03 | 91.24 | −7.5% |
| V3  Linear ST, fit C_α (cf=150000, cr=150000) | 19.42 | 9.71 | 48.33 | 91.77 | −8.1% |
| V4  V3 + Ridge residual learner (LOO) | 27.55 | 12.95 | 71.28 | 128.92 | −53.4% |

## Marginal contribution per change

- **V1 → +2.73 mrad/s drop**. The only variant that improves on V0. Almost all of the gain lives in the **straight** regime (13.31 → 7.20 mrad/s, a 45.9% drop). Interpretation: V0 contains a per-segment yaw-gyro bias that V1 explicitly subtracts on straight-line samples. The canonical wheelbase `L=2.984 m` is the same as the shipped KS, so the gyro-bias term is doing the work.
- **V2 → −4.08 mrad/s** (regression). Adding the linear-ST gain term `1/(1 + K_us v²)` with the openpilot-canonical priors hurts because (a) cornering is only ~8% of rows here so V2's understeer-correction can't pay for itself, and (b) the priors are stiff (Cα_f=286.6k, Cα_r=355.9k); on this segment set they over-shrink the predicted yaw rate. Reported as a regression with cause, not buried.
- **V3 → −0.10 mrad/s** further (marginal worse than V2). The L-BFGS-B fit landed at the seed (1.5e5 / 1.5e5) — i.e. the optimiser made no useful move. Not pegged at the upper bound, so v0.5's `pegged-at-upper` flag does not fire; the symptom here is a non-converged fit rather than a saturated bound. The skill rule of "report regression with physical reason" applies: with only 1.9k cornering rows split across 8 segments, the C_α loss surface near the seed is flat enough that L-BFGS-B exits early.
- **V4 → −8.13 mrad/s** further (largest regression). Ridge on `[v, |a_y|, |δ|, sign(δ̇)]` trained leave-one-segment-out against V3's residuals **does not generalise across segments**: each segment's per-vehicle / per-route bias is large compared to the structure Ridge can latch onto, so OOF predictions add noise to V3 rather than removing it. Per the skill: "If V4 doesn't beat V3 out-of-fold, ship V3 and call V4 a regression. Partial > faked." Honoured — V4 flagged as a regression.

## Composition decision

`regime-segmentation` first (pure DataFrame transform: load_and_validate → tag), then `lateral-fidelity-triage` for the variant ladder. The two share the same regime thresholds by convention, so per-regime RMSE numbers in the variant table come directly from `segment.per_regime_rmse`, with `lateral-fidelity-triage` supplying every prediction column and the sensor gate.

## Best variant shipped

**V1** (KS with canonical L plus per-segment straight-line gyro-bias subtraction). Sensor PASS on both checks. V2/V3/V4 not shipped — flagged as regressions on this segment set.

## Limitations

- Sample is heavily straight-dominated (92% straight rows). Cornering RMSE values move on small row counts (368 transient rows total).
- The L-BFGS-B C_α fit did not converge away from its seed; a global search or larger cornering sample would be needed to know whether a re-tuned linear ST beats V1. Reported honestly rather than re-seeded post-hoc.
- Tesla segments deliberately excluded — they have no decoded `yaw_rate_meas_rads`.
- F-150 Lightning segments not run; would require a separate ladder and a low-`v` sub-step check (skill's v0.4 warning).

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleD-m4-agent-03",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-4/agent-03/REPORT.md",
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
