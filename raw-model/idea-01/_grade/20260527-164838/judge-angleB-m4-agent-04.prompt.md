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

- agent_id: **angleB-m4-agent-04**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-4/agent-04/REPORT.md`

```markdown
# Module-4 / agent-04 (angle-B) — Lateral fidelity ladder

**Headline.** On FORD_MUSTANG_MACH_E_MK1 (315 segments, 913 626 samples, 50 Hz, clamped `v` + `δ`; predicting `yaw_rate_pred_rads` against `yaw_rate_meas_rads`), the locked V0→V4 ladder reduced overall yaw-rate-residual RMSE from **0.01613 → 0.01533 rad/s (-4.96%)**. The ladder spent more attribution surface on rejecting hypotheses than on closing the gap — the honest result is that linear-ST steady-state + first-order lag is at its ceiling for this dataset.

**Operating contract.** `v_mps` and `delta_road_rad` are **clamped to measured**; `yaw_rate_pred_rads` and `a_y_pred_mps2` are the **predicted** channels under test. Residual: `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads`. Sign sanity OK (`corr(δ, ψ̇_meas) = +0.702` on cornering).

## Variants (strict marginal V_prev→V_this on overall RMSE)

Same mask: straight `|δ|<0.01`, steady `|δ|≥0.01 ∧ |dδ/dt|<0.05`, transient `|δ|≥0.01 ∧ |dδ/dt|≥0.05`.

| # | Variant | Straight | Steady | Transient | Overall | Marginal drop | Flag |
|---|---------|----------|--------|-----------|---------|---------------|------|
| V0 | KS as-is | 0.00877 | 0.03177 | 0.05677 | 0.01613 | — | baseline |
| V1 | Per-segment gyro DC (straight-only estimator) | 0.01531 | 0.03283 | 0.05694 | 0.02010 | +0.00397 (+24.6%) | **REGRESSION** (plan-anticipated) |
| V2 | Linear ST steady-state, prior C_α | 0.00339 | 0.03432 | 0.06272 | 0.01550 | -0.00460 (-22.9%) | steady+transient regress vs V0 |
| V3 | Fit C_α (bounded 50–500 kN/rad) | 0.00339 | 0.03432 | 0.06272 | 0.01550 | 0 (0.0%) | **NEAR-MISS** (fit → priors) |
| V4 | First-order lag τ=0.08 s | 0.00314 | 0.03457 | 0.06066 | 0.01533 | -0.00017 (-1.1%) | small transient gain |

Marginal drops sum to V0→V4 total by construction.

## Painful absence

Nothing in the ladder addresses the **two-state ST dynamic eigenmodes** that the transient regime needs. Transient RMSE *grows* from V0 (0.0568) to V2 (0.0627) because steady-state ST over-predicts understeer for the actual Mach-E response, and our first-order lag (V4) can recover only 3% of that. Pacejka / dynamic-ST were out of scope.

## Near-misses

- V3 L-BFGS-B fit returned the openpilot priors *exactly* — the cornering loss surface is locally flat at the priors because residual is transient-dominated, not gain-dominated.
- V1 hypothesis rejected by its own falsification criterion: straight RMSE *rose* (0.00877 → 0.01531), proving per-segment gyro DC offset is not the dominant straight-line failure mode here.

## Surprises

1. Linear ST with openpilot-canonical priors makes cornering *worse* than KS on Mach-E — production prior assumes more understeer than the on-road data shows.
2. V3 fit declined to move from the priors at all (not pegged) — strong evidence the residual lives in dynamics, not stiffness.
3. F-150 `a_lat_meas_mps2` has `max|a_y|=1057 m/s²` — units/outlier defect; reason scored Mach-E only.
4. `parameters.py` F-150 values disagree with the skill's stated F-150 numbers — dict-vs-skill discrepancy worth reconciling.

## RPI artifacts

- Research: `rpi/runs/20260527-155843/research.md`
- Plan (locked): `rpi/runs/20260527-155843/plan.md`
- Implement notes: `rpi/runs/20260527-155843/implement-notes.md`
- Numerics: `out/ladder.json`
- Tools: `tools/research_baseline.py`, `tools/run_ladder.py`

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleB-m4-agent-04",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-4/agent-04/REPORT.md",
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
