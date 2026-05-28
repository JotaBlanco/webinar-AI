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

- agent_id: **angleC-m3-agent-04**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-3/agent-04/REPORT.md`

```markdown
# Module-3 / agent-04 (angle-C) — Lateral fidelity

## Headline

Lateral yaw-rate RMSE reduced **9.4% on Mach-E** (segment-bias variant) and **18.8% on Lightning** (per-platform affine variant), via a 4-variant ladder under RPI discipline. Surprise: the two Fords disagree on which knob matters — Mach-E is bias-dominated, Lightning is gain-dominated.

## Setting

- **Platform**: FORD_MUSTANG_MACH_E_MK1 (315 segments, 913 626 samples) + FORD_F_150_LIGHTNING_MK1 (230 segments, 667 141 samples).
- **Measured truth**: Ford has `yaw_rate_meas_rads` from CAN; Tesla does not (rule 4 — Tesla excluded).
- **Clamped vs predicted**: `v_mps` and `delta_road_rad` clamped to measured (lateral-only mode); ψ̇ and a_y predicted (rule 5).

## Variant ladder (held-out interleaved every-5th-sample TEST, rule 7)

Mach-E:

| Variant | overall | straight | steady | transient | scope |
|---|---:|---:|---:|---:|---|
| V0 baseline | 0.01613 | 0.00878 | 0.03147 | 0.05744 | — |
| V1 platform bias | 0.01614 | 0.00875 | 0.03155 | 0.05750 | per-platform |
| V2 segment bias | **0.01462** | **0.00507** | 0.03111 | 0.05756 | per-segment (**calibration**) |
| V3 steering gain k=1.110 | 0.01594 | 0.00999 | 0.03024 | **0.05085** | per-platform |
| V4 affine + bias | 0.01579 | 0.00959 | 0.03011 | 0.05214 | per-platform |

Lightning:

| Variant | overall | straight | steady | transient | scope |
|---|---:|---:|---:|---:|---|
| V0 baseline | 0.02037 | 0.00899 | 0.03629 | 0.05161 | — |
| V1 platform bias b=-4.4e-3 | 0.02006 | 0.00799 | 0.03634 | 0.05161 | per-platform |
| V2 segment bias | 0.01938 | 0.00706 | 0.03516 | 0.05128 | per-segment (**calibration**) |
| V3 steering gain k=0.892 | 0.01698 | 0.00786 | 0.02907 | 0.04485 | per-platform |
| V4 affine + bias | **0.01654** | **0.00655** | **0.02883** | 0.04540 | per-platform |

Attribution: strict marginal V0→V1→V2→V3→V4. V2 is **calibration, not model improvement** (rule 8). Honest *model* gain is V3 (per-platform): Mach-E -1.2%, Lightning -16.6%.

## Painful absence

KS has no tire side-slip, so transient residual is fundamentally limited. V3's single gain absorbs rack compliance and understeer at once — no DoF to separate them within KS. Need an ST rung.

## Near-misses / regressions

- V1 on Mach-E flat (gyro-bias hypothesis falsified for that platform).
- V3 worsens **straight** RMSE on Mach-E (0.00878 → 0.00999): k>1 amplifies near-zero δ jitter.
- V4 vs V3 on Mach-E transient regressed (0.05085 → 0.05214): bias term stole variance from gain.

## Surprise

Per-platform gain `k` is **1.110 on Mach-E but 0.892 on Lightning** — opposite signs of correction, even though shipped steer ratios are nearly identical (17.0 vs 16.9). The discrepancy lives in unmodelled rack/tire compliance, not gear ratio.

## RPI artifacts

- `rpi/runs/20260527-160000/research.md`
- `rpi/runs/20260527-160000/plan.md`
- `rpi/runs/20260527-160000/implement-notes.md`

## Eval status

- `evals/baseline_rmse.py`: matched V0 numbers exactly on both platforms.
- `evals/schema_check.py`: PASSED on `out/v4_sample_FORD_MUSTANG_MACH_E_MK1.csv` and `out/v4_sample_FORD_F_150_LIGHTNING_MK1.csv`.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleC-m3-agent-04",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-3/agent-04/REPORT.md",
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
