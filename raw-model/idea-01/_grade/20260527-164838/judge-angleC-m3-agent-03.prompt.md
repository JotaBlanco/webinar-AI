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

- agent_id: **angleC-m3-agent-03**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-3/agent-03/REPORT.md`

```markdown
# Module-3 / agent-03 (angle-C) — Lateral fidelity

**Headline.** Per-platform yaw-rate gain correction (V2) is the only variant that moves the needle. On Mustang Mach-E it cuts transient RMSE by 12.7% and steady by 6.2% but **regresses straight RMSE by +19%** (intercept leaks onto straights). On F-150 Lightning it improves every regime, dropping overall by 19.3%. V1 (static bias) is null on Mustang and small on F-150. V3 (understeer gradient) is rejected by the data — fitted K ≈ 0 on both platforms.

**Platform & truth.** Ford only: `FORD_MUSTANG_MACH_E_MK1` (315 seg / 913 626 samples) and `FORD_F_150_LIGHTNING_MK1` (230 seg / 667 141 samples). Truth channels `yaw_rate_meas_rads`, `a_lat_meas_mps2` decoded from rlog. Tesla excluded (rule 4).

**Clamped vs predicted.** `v` and `δ` are clamped to measured (lateral-only mode). Only ψ̇, a_y, x, y, ψ are predicted. Speed-state error is zero by construction (rule 5).

**Train/test.** Interleaved every-5th-sample, test = idx % 5 == 0 (rule 7). All RMSEs are TEST.

## Variant ladder — accounting: cumulative (Δ from previous rung, overall RMSE rad/s)

| Rung | Mustang overall | straight | steady | transient | F-150 overall | straight | steady | transient |
|---|---|---|---|---|---|---|---|---|
| V0 baseline | 0.01613 | 0.00878 | 0.03147 | 0.05743 | 0.02037 | 0.00899 | 0.03629 | 0.05161 |
| V1 +bias (per-platform) | 0.01616 | 0.00875 | 0.03159 | 0.05754 | 0.02007 | 0.00800 | 0.03636 | 0.05162 |
| V2 +gain (per-platform) | 0.01597 | 0.01043 | 0.02952 | 0.05013 | 0.01643 | 0.00664 | 0.02865 | 0.04472 |
| V3 +understeer-K (per-platform) | 0.01597 | 0.01044 | 0.02950 | 0.05014 | 0.01643 | 0.00664 | 0.02867 | 0.04472 |

Fits: Mustang `bias=+0.00110, a=+0.00396, b=1.0942, K=-9.6e-5`. F-150 `bias=+0.00461, a=+0.00168, b=0.8674, K=+5.6e-5`. All fits **per-platform**, not per-segment (rule 8). a_y_pred re-derived as `v·ψ̇_pred` at every rung (rule 9).

## Painful absence

Static yaw bias on Mustang is below the noise floor (1.1 mrad/s vs straight residual 8.8 mrad/s). The team's intuition that there is a sensor offset to subtract is not supported by Mustang data; on F-150 there is a small one (4.6 mrad/s).

## Near-misses

V2 helps on Mustang but the intercept `a=+0.004` leaks onto straights and inflates straight RMSE by 19% — physical cause: a single linear correction can't separate cornering gain from straight-line offset. A future V2′ would fit zero-intercept on cornering and re-bias on straights.

## Surprise

The kinematic-vs-truth gain `b` flips sign across platforms: Mustang `b=1.094` (KS under-predicts ψ̇) vs F-150 `b=0.867` (KS over-predicts). No single global multiplier works. Most likely root cause is per-platform effective steer-ratio / rack compliance — worth a follow-up that adjusts `i_s` in `code/parameters.py::PARAM_BY_PLATFORM` rather than band-aiding the prediction post-hoc.

## Regressions flagged (with physical cause)

Mustang straight RMSE +19% at V2: intercept `a` from cornering regression is non-zero on straights where the underlying residual is sensor-noise floor. Causal, not statistical — pure leakage from the variant's degree of freedom.

## RPI artifacts

- Research: `rpi/runs/20260527-160000/research.md`
- Plan (locked): `rpi/runs/20260527-160000/plan.md`
- Implement notes: `rpi/runs/20260527-160000/implement-notes.md`

## Evals

`evals/schema_check.py` PASS on `out/FORD_MUSTANG_MACH_E_MK1/sim_v3.csv` and `out/FORD_F_150_LIGHTNING_MK1/sim_v3.csv`. `evals/baseline_rmse.py` numbers match the V0 row above (overall 0.01613 / 0.02037 — rule 11 confirmed: same segment set + regime mask used at every rung).

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleC-m3-agent-03",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-3/agent-03/REPORT.md",
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
