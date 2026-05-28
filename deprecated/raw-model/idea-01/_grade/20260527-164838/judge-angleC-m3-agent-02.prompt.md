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

- agent_id: **angleC-m3-agent-02**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-3/agent-02/REPORT.md`

```markdown
# Module-3 / agent-02 (angle-C) — Lateral fidelity

**Platforms.** FORD_MUSTANG_MACH_E_MK1 and FORD_F_150_LIGHTNING_MK1. Tesla excluded — no decodable yaw-rate truth (rule 4).
**Truth channel.** `yaw_rate_meas_rads` (Ford rlog).
**Operating contract.** `clamp_v_to_measured=True`, `clamp_delta_to_measured=True` — only lateral states predicted; `v`, `δ` clamped (rule 5).
**Sign convention.** Residual = `pred − meas` (rule 1); ISO 8855 left-positive confirmed via schema_check.
**Fit scope.** Per-platform (rule 8). Interleaved every-5th-sample train/test (rule 7).

## Variant ladder (test-set RMSE, rad/s)

Mach-E (315 segs, 913 626 samples):

| Variant | overall | straight | steady | transient |
|---|---|---|---|---|
| V0 baseline | 0.01613 | 0.00878 | 0.03147 | 0.05743 |
| V1 +bias | 0.01616 | 0.00875 | 0.03159 | 0.05754 |
| V2 ×gain g=1.0948 | 0.01566 | 0.00981* | 0.02965 | 0.05020 |
| V3 gain+bias | 0.01567 | 0.00977* | 0.02977 | 0.05028 |

Lightning (230 segs, 667 141 samples):

| Variant | overall | straight | steady | transient |
|---|---|---|---|---|
| V0 baseline | 0.02037 | 0.00899 | 0.03629 | 0.05161 |
| V1 +bias b=4.6e-3 | 0.02007 | 0.00800 | 0.03636 | 0.05162 |
| V2 ×gain g=0.8677 | 0.01680 | 0.00764 | 0.02876 | 0.04475 |
| V3 gain+bias | 0.01638 | 0.00638 | 0.02874 | 0.04478 |

## Attribution (additive-bias / multiplicative-gain ladder)

- **V1 bias** captures yaw-rate sensor zero. Negligible on Mach-E (b=1.1e-3); -11% straight on Lightning (b=4.6e-3).
- **V2 gain** captures KS-vs-real lateral-gain mismatch. Dominates: Mach-E -12.5% transient / -5.8% steady; Lightning -21% steady / -13% transient. Sign **flips** between platforms (Mach-E under-predicts, Lightning over-predicts).
- **V3** stacks both; best overall on Lightning, equal to V2 on Mach-E.
- **Regression flagged:** Mach-E V2 straight +11.7% (0.00878 → 0.00981). Physical cause: a multiplicative gain on near-zero ψ̇_pred amplifies the existing straight-line noise floor — exactly the trade-off a gain-only correction should make.

## Coupled re-derivation

After scaling ψ̇_pred, `a_y_pred = v·ψ̇'` and both residual columns were recomputed (rule 9). `evals/schema_check.py` PASS on `out/FORD_MUSTANG_MACH_E_MK1/v3_sample_sim.csv` and `out/FORD_F_150_LIGHTNING_MK1/v3_sample_sim.csv`. `evals/baseline_rmse.py` V0 reproduced exactly.

## RPI artifacts

- `rpi/runs/20260527-160000/research.md`
- `rpi/runs/20260527-160000/plan.md`
- `rpi/runs/20260527-160000/implement-notes.md`
- Variant runner: `tools/run_variants.py`
- RMSE tables: `out/<PLATFORM>/variant_rmse.csv`

## Headline

Per-platform multiplicative gain on ψ̇_pred is the lever; bias is a thin second-order term. Mach-E overall RMSE 0.01613 → 0.01567 (-2.9%), transient -12.5%. Lightning 0.02037 → 0.01638 (-19.6%), transient -13%, straight -29%.

## Painful absence

No tire-slip / yaw-lag term — transient RMSE remains 5-6× straight even after gain. A first-order ψ̇-lag would be V4, deliberately deferred (out of 15-min budget).

## Near-misses

(a) V2 regresses Mach-E straight by 12% — multiplicative gain amplifies noise floor; (b) per-segment fit would have shaved more but is calibration, not model improvement (rule 8).

## Surprise

Gain sign flips between Ford platforms (Mach-E g=1.095 under-predicts; Lightning g=0.868 over-predicts) despite both using canonical openpilot `carParams`. A single global wheelbase/i_s correction would not have worked — fit must be per-platform.

## Eval status

`schema_check.py` PASS on both V3 sample CSVs; `baseline_rmse.py` V0 reproduces canonical numbers.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleC-m3-agent-02",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-3/agent-02/REPORT.md",
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
