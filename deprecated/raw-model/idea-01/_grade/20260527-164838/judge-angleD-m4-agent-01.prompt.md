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

- agent_id: **angleD-m4-agent-01**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-4/agent-01/REPORT.md`

```markdown
# REPORT.md — lateral-fidelity triage, module-4 / agent-01

- **Platform:** `FORD_MUSTANG_MACH_E_MK1` (Mach-E MK1). `yaw_rate_meas_rads` is **measured truth** decoded from the openpilot rlog IMU; not a derived channel.
- **Contract:** speed-known, lateral-only. `v_mps` and `delta_road_rad` are **clamped to measured** at each KS step (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Speed-state agreement is zero by construction and is not in scope.
- **Residual under test:** `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads`.
- **Segment set:** 12 Mach-E segments, 34 860 rows. Regime counts: 29 907 straight / 4 148 steady cornering / 805 transient cornering.
- **Skills composed:** `regime-segmentation` (tags `regime` column from `δ`, `dδ/dt`) → `lateral-fidelity-triage` (variant ladder). Lockstep check `triage.regime_mask` vs `segment.tag` = 1.0000 agreement.
- **Attribution scheme:** strict marginal, fixed order V0→V1→V2→V3→V4. Sum of marginals = 0.00042 rad/s = total drop V0→V4 (within 15 % — telescoping holds, no overlap).
- **Sensor gate:** PASSED on best variant V1. `corr(pred, meas)` on cornering = 0.997 (> 0). `RMSE(V1) = 0.00885 ≤ RMSE(V0) = 0.01082`.

## Variant ladder

| Variant | Overall RMSE (rad/s) | Straight | Steady cornering | Transient cornering | Marginal Δ vs prev | Verdict |
|---------|---------------------:|---------:|-----------------:|--------------------:|-------------------:|---------|
| V0 — pre-computed residual, no preprocessing | 0.01082 | 0.00803 | 0.01774 | 0.03242 | — | baseline |
| V1 — KS recalibrated + per-segment straight-line yaw-gyro de-bias | **0.00885** | 0.00365 | 0.01796 | 0.03516 | **−0.00197** | **best, ship** |
| V2 — Linear ST, prior Cα (openpilot-canonical Mach-E values) | 0.01028 | 0.00318 | 0.02193 | 0.04144 | +0.00142 | **regression vs V1** — prior stiffness over-rotates this dataset on cornering |
| V3 — Linear ST, fit Cα (grid search, bounds 5e4–5e5 N/rad) — `C_αf=334 295`, `C_αr=318 109`, not pegged | 0.00951 | 0.00300 | 0.02010 | 0.03877 | −0.00076 | partial recovery vs V2, still **regression vs V1** |
| V4 — Ridge residual learner on V3 residuals, leave-one-segment-out CV | 0.01040 | 0.00344 | 0.02359 | 0.03710 | +0.00089 | **regression** — OOF RMSE = 0.01040 > V3, does not generalise; shipped as V3 not V4 per skill rule |

## Per-variant notes

- **V1.** All gain is in the straight regime (0.00803 → 0.00365 rad/s). Cornering regimes worsen slightly because the constant per-segment bias is removed uniformly while cornering residuals are not bias-dominated. Honest physical reading: this is a gyro-bias correction, not a model-fidelity upgrade.
- **V2.** ST with the openpilot-canonical prior Cα makes straights marginally better (0.00318) but trades it back two-fold in steady and transient cornering. Cause: the prior Cα is calibrated for openpilot's lane-keeping operating point, which is stiffer than this set of segments needs; ST then under-predicts steady cornering yaw rate.
- **V3.** Grid-search fit lands at `C_αf=334 295`, `C_αr=318 109` N/rad — *not* pegged at the 5e5 upper bound, so v0.5's pegged-Cα warning does not fire. Helper limitation: `triage.fit_c_alpha`'s default `L-BFGS-B` step is below O(1e5) numerical resolution and returns `x0` unchanged. The grid-search wrapper in `tools/run_ladder.py` replaces it. Methodology is unchanged; the helper deserves a future patch.
- **V4.** Ridge on `[v, |a_y|, |δ|, sign(δ̇)]` against V3 residuals. LOO OOF RMSE (0.01040) > V3 (0.00951), so by the skill's own rule, V4 is a regression and we ship V3-as-floor, V1-as-best. The learner has no generalisable signal at this segment count.

## Headline findings

- Best variant V1, overall RMSE 0.00885 rad/s, an 18.2 % drop vs V0.
- The win is a **straight-line gyro-bias artefact**, not a tyre/stiffness modelling improvement. Cornering RMSE actually *worsens slightly* under V1.
- More physics (V2, V3) hurts on this Mach-E subset; openpilot's prior Cα is too stiff for these segments, and even fit Cα doesn't claw back the cornering regressions vs V1.
- The Ridge residual learner (V4) does not generalise out-of-fold — shipped as V3 floor, not V4.
- Sum of strict-marginal drops V0→V4 = 0.00042 = total drop V0→V4 (exact telescope, well within 15 % tolerance).

## Composition and limitations

- Composed `regime-segmentation` upstream of `lateral-fidelity-triage`. The regime-tagged DataFrame fed every per-regime RMSE column. Both skills share thresholds (`|δ|<0.01`, `|dδ/dt|<0.05`) — verified 1.0000 lockstep agreement at runtime.
- Limitations / declared scope: only 12 Mach-E segments used (315 available); no Lightning segments used (Lightning's stationary stretches would stress the v_min ST fallback differently). `fit_c_alpha` helper bug worked around with a grid search.
- Sensor gate: PASSED.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleD-m4-agent-01",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-4/agent-01/REPORT.md",
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
