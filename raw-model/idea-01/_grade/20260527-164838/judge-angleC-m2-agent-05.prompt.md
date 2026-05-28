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

- agent_id: **angleC-m2-agent-05**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-2/agent-05/REPORT.md`

```markdown
# Module-2 / agent-05 (angle-C) — Lateral fidelity

## Platform & truth

Scored on **FORD_MUSTANG_MACH_E_MK1** (315 segments). `yaw_rate_meas_rads` is the measured truth channel decoded from the rlog IMU; Tesla excluded per AGENTS.md rule 4 (no decodable yaw-rate truth).

ISO 8855 sanity: `corr(delta_road, yaw_rate_meas)` on cornering = **+0.790** (expected positive).

## Operating contract

`v` and `δ` are **clamped to measured**, not predicted. Only lateral states (ψ, ψ̇, a_y) are under test.

## Variant ladder

Per-platform fit, interleaved 5-way split, test-only RMSE of yaw-rate residual (rad/s):

| Variant | all | straight | steady-corner | transient-corner |
|---|---:|---:|---:|---:|
| V0 baseline (`yaw_rate_resid_rads` as-is) | 0.01613 | 0.00820 | 0.03100 | 0.04832 |
| V1 bias removal (b = +0.00075 rad/s) | 0.01614 | 0.00817 | 0.03170 | 0.04694 |
| V2 steer-gain k = 1.0843 | **0.01561** | 0.00881 | 0.03107 | **0.04005** |
| V3 lag align (+40 ms) | 0.01624 | 0.00905 | 0.03173 | 0.04393 |

Fit discipline: all variants are **per-platform**, fit on the train fold (4/5 of samples, interleaved), reported on the held-out test fold. Same segment set, same regime masks across rows (straight: |ψ̇|<0.03; transient: cornering with |dψ̇/dt|≥0.10).

## Strict marginal accounting (V0 → V_last, "all" RMSE)

- V1 bias removal: Δ = -0.08% (bias is ~0; ISO sign already correct upstream).
- V2 steer-gain: Δ = +3.29% improvement (transient-corner RMSE drops 17%: 0.0483 → 0.0401).
- V3 lag align: Δ = -3.92% (regression).
- Net V0 → V3: -0.72% overall. V2 alone delivers +3.3% net.

## Regressions (with physical cause)

- **V3 lag-align (+40 ms) regresses.** Cause: Mach-E KS prediction is in-phase with measured ψ̇ once V2's gain correction is applied; the residual transient-cornering error is amplitude, not timing. Shifting by ±2 samples decorrelates steady-state cornering peaks more than it aligns transients. The minimiser on the cornering subset picked +40 ms; on **all** samples it hurts straight-line noise.
- **V1 bias is effectively zero** (+0.75 mrad/s ≈ 0.04 deg/s). The Ford IMU is well-zeroed; bias removal is a no-op on this platform.

## Coupled `a_y` note

`a_y_pred = v · ψ̇`. Any operational use of V2 must re-derive `a_y_pred_mps2 = v·(k·ψ̇_v1)` and recompute `a_y_resid_mps2`. Not re-scored here; V2 propagates to a_y by the same +8.4% gain on ψ̇.

## Painful absence

No per-segment IMU offset table to test rule 8's "calibration vs improvement" distinction — per-platform fit is the only honest framing.

## Near-misses

Lag alignment looked promising on cornering-only train subset (best_lag=+40 ms, lower train RMSE) but failed out-of-fold — classic over-fit to autocorrelated cornering peaks (rule 7 trap, almost re-paid).

## Surprise

Bias is genuinely zero on Mach-E. Dominant error is a **steering-gain under-prediction of ~8%** — KS with openpilot-canonical i_s=17.0 systematically under-rotates the Mach-E in transient cornering. Either i_s is closer to 15.7 in practice, or compliance steer (tire/bushing) is adding ~8% effective δ at the road wheel that KS doesn't model.

Files: `tools/ladder.py`, `out/ladder.csv`.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleC-m2-agent-05",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-2/agent-05/REPORT.md",
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
