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

- agent_id: **angleB-m3-agent-01**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-3/agent-01/REPORT.md`

```markdown
# Module-3 / agent-01 (angle-B) — Lateral Fidelity, FORD_MUSTANG_MACH_E_MK1

**Platform:** `FORD_MUSTANG_MACH_E_MK1` (Tesla excluded — no IMU truth; F-150 not used to keep one platform per ladder).
**Operating contract:** `v` and `δ` clamped to measured each step. Predicted channel = `yaw_rate_pred_rads`. Truth = `yaw_rate_meas_rads`. Metric = RMSE of `pred − meas` over 315 segments / 913 626 samples at 50 Hz.
**Sign check:** `corr(delta_road, yaw_rate_meas)` on cornering = **+0.702** — convention OK.
**Accounting scheme:** sequential marginal drop on `all` regime RMSE; marginal sum vs total V0→V4 gap = -1.2% (well inside 15%).

## Variant ladder (rad/s RMSE)

| Variant | all | straight | steady | transient | marginal drop |
|---|---:|---:|---:|---:|---:|
| V0 KS baseline | 0.01613 | 0.00877 | 0.03173 | 0.05680 | — |
| V1 KS + per-seg straight-line bias | 0.01469 | 0.00493 | 0.03168 | 0.05730 | -0.00143 |
| V2 ST steady-state, prior C_α | 0.01551 | 0.00339 | 0.03430 | 0.06277 | +0.00082 (regression) |
| V3 ST steady-state, fit C_α (50–500 kN/rad) | 0.01551 | 0.00339 | 0.03430 | 0.06277 | 0.00000 |
| V4 V3 + LOSO Ridge on [v,\|a_y\|,\|δ\|,sign(δ̇)] | 0.01530 | 0.00346 | 0.03393 | 0.06148 | -0.00021 |

**Headline:** V0→V4 drop = 0.0008 rad/s (~5%), almost all of it from V1's per-segment yaw-gyro bias removal. ST didn't help.

## What each contributed

- **V1 (-0.00143):** Per-segment straight-line yaw-gyro bias slashes straight-regime RMSE 44% (0.00877 → 0.00493) and is the only honest win.
- **V2 regression (+0.00082):** Linear-ST steady-state gain with openpilot's prior C_α *under-rotates* the car vs KS on steady and transient regimes. Priors 287/356 kN/rad — likely too stiff for these tyres/roads.
- **V3 (0.00000):** L-BFGS-B with bounds [50, 500] kN/rad **stayed exactly at the priors**. Not pegged — the MSE surface on steady-cornering RMSE has a local minimum at the prior. Linear-ST form lacks the DoF to beat V1 with bounded C_α. Diagnosis: **wrong form**, not wrong calibration window.
- **V4 (-0.00021):** Ridge residual learner under LOSO recovers small transient-regime drop (0.06277 → 0.06148) — picks up steering-rate-dependent residual KS/ST can't model.

## Painful absence

No tyre slip and no inertia: KS has `ψ̇ = (v/L)·tan(δ)`, so the **transient regime (0.057 rad/s RMSE, ~3.5× steady)** is structurally unreachable. The KS→ST step does not close it because the linear ST is still a steady-state algebraic gain with no `I_z·dψ̇/dt` term. Closing transients needs a proper ST ODE (Pacejka or dynamic linear-ST) — out of scope per the skill.

## Rule-prevented near-misses

- Defaulting to Tesla for "more segments" — blocked by truth-channel matrix.
- Unclamping v/δ — blocked by contract.
- Reading `delta_wheel_deg` as radians — would have produced ~15× error.
- In-fold scoring of the Ridge residual learner — used LOSO; in-fold would have laundered ~70% of V0 residual dishonestly.
- Different segment set across rungs — same 315-segment Mach-E set used for every variant.

## Most surprising

**The bounded C_α fit refused to move from the openpilot priors.** Not pegged at a bound, not numerical failure — the steady-cornering MSE has a local minimum at the priors and the linear-ST form is simply the wrong model class for these segments. The V2 regression flag is real and structural, not a calibration nit. The honest read: V1 (bias correction) is the only rung that helped; the ST rung as specified is a dead end; next real win lives at Pacejka or the dynamic linear-ST ODE.

Files: `tools/lateral_fidelity.py`, `out/lateral_fidelity_summary.json`.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleB-m3-agent-01",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-3/agent-01/REPORT.md",
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
