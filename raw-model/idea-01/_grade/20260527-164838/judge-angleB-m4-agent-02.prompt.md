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

- agent_id: **angleB-m4-agent-02**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-4/agent-02/REPORT.md`

```markdown
# Module-4 / agent-02 (angle-B) — Lateral fidelity ladder

**Platform scored:** `FORD_MUSTANG_MACH_E_MK1` (315 segments, 913 626 samples @ 50 Hz). Lightning has truth too but Mach-E has the larger set. Tesla excluded — no IMU truth channel.

**Clamped vs predicted:** `v_mps` and `delta_road_rad` are inputs (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). The channel under test is `yaw_rate_pred_rads`; truth is `yaw_rate_meas_rads`; residual `pred − meas`.

**Sign sanity:** `corr(δ_road, ψ̇_meas)` on cornering = **+0.702**. ISO 8855 intact.

**Regime mask** (fixed): straight `|δ|<0.01`; steady `|δ|≥0.01 ∧ |δ̇|<0.05`; transient `|δ|≥0.01 ∧ |δ̇|≥0.05`. Counts: 785 093 / 107 055 / 21 478.

## Variant ladder (locked V0 → V3, strict marginal accounting on all-regime RMSE)

| # | Variant | all RMSE | straight | steady | transient | Δ all | named drop |
|---|---|---|---|---|---|---|---|
| V0 | KS baseline (`yaw_rate_resid_rads` as-is) | 0.01613 | 0.00877 | 0.03172 | 0.05689 | — | — |
| V1 | + per-segment straight-line bias | 0.01469 | 0.00493 | 0.03167 | 0.05739 | **-0.00143** | seg-bias |
| V2 | linear-ST gain, prior C_α (Mach-E openpilot) | 0.01551 | 0.00339 | 0.03429 | 0.06287 | **+0.00082** | ST-prior (regression) |
| V3 | linear-ST, fit C_α | 0.01515 | 0.00411 | 0.03308 | 0.06082 | **-0.00036** | ST-refit |

**Accounting:** strict marginal, fixed V0→V3 order, all-regime RMSE. Total drop V0→V3 = -0.000972; sum of marginals = -0.000969; within 0.3% — well inside 15% tolerance. No double-counting.

**Fitted stiffnesses (V3):** C_αf = 187 584 N/rad (65% of prior), C_αr = 154 703 N/rad (43% of prior). Neither pegs the 50–500 kN/rad bounds.

## Honest regression flags

- **V2 is a regression on cornering** (+8% steady, +10% transient). Openpilot's prior C_α understeers the Mach-E *more* than KS does on these roads. The straight-line improvement at V2 comes from re-fitting the per-segment bias against a worse predictor; it should not be read as a model upgrade.
- **V3 recovers most but not all of the V2 cornering regression**: steady 0.03308 (V3) vs 0.03167 (V1); the refit ST never beats KS+bias on this dataset.
- **Headline credit:** V1 alone delivers ~146% of the eventual V0→V3 drop. The cheap fix wins.

## RPI artifacts

- Research: `rpi/runs/20260527-155834/research.md`
- Plan: `rpi/runs/20260527-155834/plan.md`
- Implement: `rpi/runs/20260527-155834/implement-notes.md`
- Code: `tools/eval_lateral.py`. Numeric output: `out/lateral_eval.json`.

## Painful absence

A non-linear tyre rung (V4 Pacejka) is needed to test whether the *form* of the linear-ST gain is wrong on transient steering — V3 still loses to V1 on transient cornering (0.0608 vs 0.0574). Out of scope at 15 min.

## Near-miss

V3 closes to within 0.0004 rad/s of V1 on all-regime — going from KS+bias to a 2-parameter fitted linear-ST model is statistically a wash on this data.

## Surprise

Fitted C_αr (155 kN/rad) is **43%** of the openpilot prior (356 kN/rad). Either the rear tyres slip far earlier than openpilot's canonical value claims, or — more likely — the linear-ST steady-state gain is absorbing model error it has no physical right to absorb. Treat the V3 stiffnesses as a calibration fudge, not a measurement.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleB-m4-agent-02",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-4/agent-02/REPORT.md",
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
