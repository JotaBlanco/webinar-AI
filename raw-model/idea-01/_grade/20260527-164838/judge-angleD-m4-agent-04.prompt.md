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

- agent_id: **angleD-m4-agent-04**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-4/agent-04/REPORT.md`

```markdown
# REPORT.md — webinar-angle-D / module-4 / agent-04

## Task
"Lateral predictions from our vehicle model aren't as good as they should be. Make them better, and tell me how much each change contributed."

## Setup
- Platform: **FORD_MUSTANG_MACH_E_MK1** (Mach-E). `yaw_rate_meas_rads` is the **measured** truth channel from the openpilot rlog IMU.
- Operating contract: `v` and `δ` are **clamped to measured** every step (speed-known, lateral-only). Speed-state agreement is zero by construction and is not the metric.
- Segment set: 8 distinct routes under `data/sim/segments/FORD_MUSTANG_MACH_E_MK1/` (first sim.csv per route), 23,189 rows total. Regime split: 19,581 straight / 2,723 steady / 885 transient.
- Skills composed: `regime-segmentation` (tag the DF) → `lateral-fidelity-triage` (ladder + sensor).
- Attribution: **strict marginal**, fixed order V0→V1→V2→V3→V4. Marginal drops sum to the total V0→V4 drop within < 1% — accounting is consistent.

## Variant ladder

| Variant | Description | Overall RMSE (rad/s) | Straight | Steady | Transient | Marginal Δ vs prev | Verdict |
|---|---|---|---|---|---|---|---|
| V0 | As-is `yaw_rate_resid_rads` baseline | 0.01704 | 0.00913 | 0.03128 | 0.05246 | — | baseline |
| V1 | KS recalibrated (canonical L) + per-segment yaw-gyro bias on straight samples | **0.01635** | 0.00480 | 0.03246 | 0.05704 | **+0.00069 (improves)** | **best — shipped** |
| V2 | Linear single-track, prior `C_α` (Cαf=286551, Cαr=355912 N/rad) | 0.02051 | 0.00376 | 0.04317 | 0.07055 | −0.00416 (regresses) | regression |
| V3 | Linear single-track, fitted `C_α` (Cαf=150000, Cαr=150000 — optimiser stalled at init) | 0.02067 | 0.00380 | 0.04358 | 0.07092 | −0.00016 (regresses) | regression |
| V4 | Ridge residual learner on `[v, |a_y|, |δ|, sign(δ̇)]`, LOO-by-segment, subtracted from V3 | 0.02751 | 0.00439 | 0.05675 | 0.09743 | −0.00684 (regresses) | regression |

## What contributed to the improvement
- The whole net improvement (−0.00069 rad/s overall, **−0.00433 in the straight regime**) comes from V1: canonical wheelbase + per-segment gyro-bias subtraction on straight-line samples. Bias removal halves straight-regime RMSE; that dominates the row-weighted overall.
- V2/V3/V4 all made things worse. Reasons:
  - **V2 (prior Cα)**: linear-ST with stiff prior under-predicts yaw rate in cornering. Cornering RMSE in steady regime jumps 0.031 → 0.043, transient 0.052 → 0.071.
  - **V3 (fitted Cα)**: `fit_c_alpha` minimises overall RMSE which is dominated by 84% straight-line rows that carry no Cα signal. Optimizer stalled at the x0 init (1.5e5, 1.5e5); `pegged=False` only because pegging is defined at the *upper* bound. This is a real failure of fit scoping — fitting should be done over the cornering subset only.
  - **V4 (residual learner)**: LOO-OOF RMSE on V3 residual is 0.0275 — far worse than V3 in-sample. The learner cannot generalise across routes on these features; correctly flagged a regression per the v0.5 LOO-honesty rule.

## Sensor gate
`python3 skills/lateral-fidelity-triage/sensor.py out/best_V1.csv`
- sensor PASS sign-consistency: corr(pred, meas) on cornering = 0.995
- sensor PASS regression-check: RMSE(candidate) = 0.01635 ≤ V0 = 0.01704

V1 is shippable.

## Skill composition decision
- Order: `regime-segmentation.load_and_validate` → `.tag` → pass tagged DF into the ladder. Both skills share identical regime thresholds (`|δ|<0.01` rad, `|dδ/dt|<0.05` rad/s); kept in lockstep by convention.
- Justification: regime-segmentation is a pure DataFrame transform with no platform knowledge; lateral-fidelity-triage is the analytical playbook. Front-loading the deterministic tagger means every ladder row uses the same regime labels as the reporting layer.

## Honest limitations / painful absences
- **No `a_y` track in either skill.** Data carries `a_y_pred_mps2` and `a_y_resid_mps2` but the ladder only scores yaw rate. Lateral fidelity has two channels; we improved one.
- **Cα fit not regime-scoped.** `triage.fit_c_alpha` minimises over all rows; for an 84%-straight dataset that has no useful Cα gradient. A v0.6 patch would fit on the `regime != "straight"` slice.
- **No third "reporting" skill.** Variant orchestration + report writing lives in `tools/run_ladder.py` (per-agent script). Two-skill harness, three-skill problem.
- Read only the files inside `module-4/agent-04/` plus the symlinked `code/` and `data/`. No siblings, no other angles, no `_shared` or `_launch` or `raw-model`.

## Rules that earned their keep
- v0.3 V0-baseline pin: stopped the gyro-bias from being folded into V0 (which would have hidden V1's win entirely).
- v0.5 pegged-Cα + regression-flagging rules: forced honest reporting of V2/V3/V4 as regressions, not silent wins.
- v0.5 sensor.py gate: deterministic sign/regression guard on the shipped variant.
- LOO-only scoring for V4: surfaced the residual learner's failure to generalise.

## Surprise
V2/V3 worsen cornering despite being a "better" physics model. The headline is that **the dataset's row-weight is so heavily straight-driving that the Cα fitter has no signal**; the linear-ST prior under-predicts cornering yaw rate; the simpler KS + bias-zero correction (V1) wins. Composition exposed this because the regime tagger made the row imbalance visible in the table — without the per-regime breakdown, "V3 is a regression" would have been buried under a flat overall RMSE.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleD-m4-agent-04",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-4/agent-04/REPORT.md",
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
