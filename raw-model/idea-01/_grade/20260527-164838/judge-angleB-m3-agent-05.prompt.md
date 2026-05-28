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

- agent_id: **angleB-m3-agent-05**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-3/agent-05/REPORT.md`

```markdown
# Module-3 / agent-05 (angle-B) — Lateral fidelity ladder

**Platform:** `FORD_MUSTANG_MACH_E_MK1` (Ford required for lateral truth; Tesla has no yaw-rate measurement). 306 segments, 810 208 samples at 50 Hz after `v ≥ 2 m/s` gate.

**Clamped vs predicted:** `v` and `δ_road` are clamped to measurement (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Predicted channel under test is `yaw_rate_pred_rads`. Metric is RMSE of `yaw_rate_pred − yaw_rate_meas_rads`. Sign sanity: `corr(δ_road, ψ̇_meas)` on cornering = **+0.922** (correct).

## Variant ladder (cumulative, same segment set, same regime mask)

| Variant | Description | RMSE all | straight | steady | transient | Marginal drop |
|---|---|---:|---:|---:|---:|---:|
| V0 | KS baseline (CSV as-is) | 0.01316 | 0.00912 | 0.02438 | 0.04362 | — |
| V1 | V0 + per-segment straight-line bias (IMU gyro offset) | **0.01105** | 0.00511 | 0.02401 | 0.04404 | **-0.00211** |
| V2 | Linear ST, prior C_α (openpilot) + per-seg bias | 0.01225 | 0.00348 | 0.02855 | 0.05213 | +0.00121 (regression) |
| V3 | Linear ST, fit C_α (bounded 50–500 kN/rad) + per-seg bias | 0.01166 | 0.00365 | 0.02663 | 0.04996 | -0.00059 |

Total drop V0→V3 = -0.00150 rad/s (≈11% of V0). Sum of marginals = -0.00150 — exact, no double-counting. Accounting scheme: **last-rung-wins** (each marginal is `RMSE(V_{n−1}) − RMSE(V_n)` on the full all-regime pool).

## Findings, named

- **Painful absence — slip.** KS has no tyre slip. Cornering residual (steady 0.024, transient 0.044 rad/s) is what an ST/Pacejka rung *could* close. The ST upgrade here doesn't, because the openpilot prior C_α is calibrated for very sticky OE rubber and the residual structure suggests less stiff effective tyres on this test data.
- **The win that mattered — IMU bias.** V1 alone removed 16% of V0 RMSE, almost entirely from the straight regime (0.00912 → 0.00511). Per-segment yaw-gyro offset masquerading as model error. One DOF per segment, free improvement.
- **Near-miss — fit C_α.** V3 lands at C_αf ≈ C_αr ≈ 400 kN/rad (interior, **not** pegged at the 500 kN/rad bound). It claws back ~half of V2's cornering regression but never beats V1. The linear-ST form is the wrong shape, not just wrong-prior.

## Honest regression flags

- V2 regresses against V1 on every cornering regime (steady +19%, transient +18%). The prior stiffnesses make steady-state yaw gain too large at the speeds in this fleet.
- C_α fit is **not pegged** at the upper bound, but symmetric front=rear=400 kN/rad beating both the asymmetric prior and physical front/rear split is a soft red flag of its own — likely tyres-saturating at moderate `|a_y|` that the linear form cannot capture.

## What I did not do

- No residual learner (out of scope — would need LOSO CV to be honest).
- No Pacejka — out of scope per skill notes.
- F-150 Lightning not scored to avoid mixing platforms in one ladder.

## Headline

**The biggest lateral-fidelity win was not a model upgrade — it was per-segment IMU yaw-gyro bias removal (-0.00211 rad/s, ~16% of V0). Climbing to linear ST with openpilot's production C_α priors *regresses* cornering RMSE by ~19%; refitting C_α partially recovers but never beats the bias-corrected KS. The linear-ST form, not just the priors, is the wrong rung for this data.**

Files: `tools/run_ladder.py`, `out/ladder_results.json`.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleB-m3-agent-05",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-3/agent-05/REPORT.md",
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
