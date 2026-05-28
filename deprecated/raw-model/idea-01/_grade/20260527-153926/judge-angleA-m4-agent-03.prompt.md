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

- agent_id: **angleA-m4-agent-03**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-4/agent-03/REPORT.md`

```markdown
# Module-4 / agent-03 — Lateral-fidelity ladder (Ford Mustang Mach-E MK1)

## Platform, channels, contract

- Platform: **FORD_MUSTANG_MACH_E_MK1** — 315 sim.csv segments, 913 626 samples at 50 Hz.
- Scored channel: `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads`. `yaw_rate_meas_rads` is the **measured** truth channel decoded from the rlog gyro; it is not predicted and is not clamped.
- Speed-known contract: `v` and `δ` are **clamped** to the measured values in the KS integrator. The **predicted** quantity under test is `yaw_rate_pred_rads` (V0) and its V1–V4 re-predictions. Speed-state agreement is zero by construction and is not the metric.
- Sign sanity check: `corr(δ_road, ψ̇_meas) = +0.702` on cornering samples. Convention is correct.
- Methodology: same segment set and same regime mask **held constant across every variant row**. Regimes: `straight` (`|δ_road|<0.01`), `steady` (`|δ_road|≥0.01 ∧ |δ̇|<0.05`), `transient` (`|δ_road|≥0.01 ∧ |δ̇|≥0.05`). All RMSE values in rad/s on `yaw_rate_resid_rads`. Negative `Δ` means RMSE went down (improvement).

## Variant ladder

| Variant | Description | RMSE overall | Straight | Steady | Transient | Δ vs prev |
|---|---|---:|---:|---:|---:|---:|
| V0 | Baseline `yaw_rate_resid_rads` as-is, no preprocessing                                                                                                  | 0.016127 | 0.008768 | 0.031724 | 0.056889 | — |
| V1 | KS recalibrated with canonical `L=2.984`; minus per-segment yaw-gyro bias on straights                                                                  | 0.014693 | 0.004931 | 0.031673 | 0.057390 | -0.001434 |
| V2 | Linear single-track with openpilot prior `C_αf=286 551, C_αr=355 912`, KS fallback below 2 m/s, same per-segment bias                                   | 0.015512 | 0.003393 | 0.034294 | 0.062869 | +0.000819 (regression) |
| V3 | Linear ST with `C_α` fit by differential evolution on the full segment set, bounded (5e4,5e5) N/rad → `C_αf=401 575, C_αr=389 774` (not pegged)         | 0.015105 | 0.003645 | 0.033124 | 0.061242 | -0.000407 |
| V4 | Ridge residual learner on V3 residuals; features `[v, |a_y|, |δ|, sign(δ̇)]`; **leave-one-segment-out** out-of-fold predictions                          | 0.014897 | 0.003704 | 0.032705 | 0.060063 | -0.000208 |

**Attribution scheme:** strict marginal, fixed order V0→V1→V2→V3→V4. Total drop V0→V4 = 0.001230 rad/s; signed Σ of the Δ column = -0.001230; `|Σmarg − total|/total ≈ 0.000` (well under the 15% coherence threshold).

## Findings, regression, and physical interpretation

- **Headline result.** Overall yaw-rate RMSE dropped from V0 = 0.016127 rad/s to V4 = 0.014897 rad/s — a **7.6% relative improvement** on the full Mach-E set. Most delivered by V1 alone (per-segment yaw-gyro bias) on the *straight* regime, where bias removal nearly halves residual RMSE (0.00877 → 0.00493).
- **V2 regressed against V1** (overall +0.000819). This is the predicted Mach-E behaviour: the openpilot ST prior `C_α` values are **stiffer than this car's tyres actually behave**, so the steady-state ST gain over-corrects KS and worsens both cornering regimes (steady 0.0317 → 0.0343; transient 0.0574 → 0.0629). V2 *does* improve straight (0.0049 → 0.0034) because the steady-state-gain form yields exactly zero yaw at zero δ, but the cornering damage dominates. **Regression flagged with cause: stiff prior `C_α` mis-matches Mach-E lateral compliance.**
- **V3 recovers part of the V2 regression but does not return to V1.** DE fit pushed both stiffnesses up toward (but not at) the 5e5 ceiling, reflecting that the joint loss "wants" the ST gain to look more like KS. V3 still under-performs V1 because linear-ST has one effective steady-state knob (`K_us`) and cannot reproduce the per-regime structure a bias-corrected KS captures.
- **V4 adds a small honest gain.** LOO-CV ridge residual learner trims another 0.000208 rad/s, mostly in steady and transient cornering — consistent with picking up a low-order `|a_y|`-dependent slip-angle correction that neither KS nor linear-ST encode. With in-fold scoring V4 would look much larger; LOO discipline keeps it honest.

## Workshop lesson

A single per-segment bias subtraction (V1) yields the bulk of the available improvement (1.43 mrad/s). Going to ST (V2) actively hurts on this platform's prior; the fit (V3) recovers most but not all of the damage; the residual learner (V4) adds a small honest top-up. The ladder's most useful output here is the *attribution column itself*: it shows which rungs pay and which cost.

## Methodological note

The bare `triage.fit_c_alpha` (L-BFGS-B from a single x0) gets stuck because the per-segment-bias step makes the loss surface non-smooth. Used differential evolution in `out/run_ladder.py` to find the global minimum. Helper should be patched.

## Limitations

- Only **FORD_MUSTANG_MACH_E_MK1** scored to keep segment-set constant. F-150 Lightning would be a useful cross-platform check but mixing platforms breaks methodology-consistency.
- V4 uses `a_y_pred_mps2` (KS prediction, no slip) as a feature per SKILL spec. Swapping in `a_lat_meas_mps2` could improve the learner but would change the variant definition.
- Per-segment bias in V1 absorbs both real gyro offset and any constant-δ steering-ratio mis-calibration; the two are not separately identifiable from straight-line data.

Files: `out/run_ladder.py`, `out/ladder_draft.md` (eval 6/6 PASS).

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleA-m4-agent-03",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-4/agent-03/REPORT.md",
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
