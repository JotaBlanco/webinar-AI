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

- agent_id: **angleC-m2-agent-03**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-2/agent-03/REPORT.md`

```markdown
# Module-2 / agent-03 (angle-C) — Lateral fidelity ladder

## Headline

On 315 Mach-E segments, the lateral-yaw-rate ladder went from RMSE 0.924 deg/s (V0) → 0.879 deg/s (V3) on a held-out interleaved test set — a 4.9% global cut, driven almost entirely by an 80 ms time-alignment and a +8.5% steering-gain scaler. Bias removal was a wash.

## Variants (strict marginal, V0→V3, per-platform fits)

| Variant | all | straight | steady | transient |
|---|---:|---:|---:|---:|
| V0 baseline (`yaw_rate_resid_rads` as-is) | 0.9242 | 0.4776 | 1.3386 | 2.6357 |
| V1 + bias (median pred-meas on train-straight = +0.00127 rad/s) | 0.9260 | 0.4753 | 1.3451 | 2.6424 |
| V2 + lag (median 4 samples = 80 ms, per-segment, train-half xcorr) | 0.9112 | 0.4679 | 1.3452 | 2.5535 |
| V3 + steering-gain k=1.0848 (per-platform LS, cornering-train) | **0.8787** | 0.5048 | 1.3370 | **2.2155** |

Marginal Δ on RMSE_all (deg/s, % of V0):
- V1 bias: -0.002 (-0.2%) — negligible
- V2 lag: +0.015 (+1.6%)
- V3 gain: +0.033 (+3.5%)

Total improvement V0→V3: **0.046 deg/s = 4.9% of baseline**; on the transient regime the improvement is **16%**.

Train/test discipline: every-5th-sample interleaved split (rule 7). All variants share segment set and regime masks. Bias and gain are **per-platform** fits; lag is **per-segment**. Platform: **FORD_MUSTANG_MACH_E_MK1** (`yaw_rate_meas_rads` is measured truth, IMU-decoded; `v`, `δ` clamped to measured, only lateral states predicted per rule 5). Sign check: `corr(δ_road, ψ̇_meas) = +0.702` on cornering — ISO 8855 holds.

## Painful absence

A KS model with no tyre slip cannot reproduce the **transient phase lag** between steering input and yaw rate — that's exactly the 80 ms shift V2 recovers. The model also under-predicts yaw amplitude by ~8% across the platform (V3's k=1.085) — consistent with KS assumption of zero slip angle at the rear axle understating gain at the speeds in this fleet.

## Near-misses

- Per-platform median bias was only 0.00127 rad/s (0.073 deg/s) — well below the straight-line noise floor, so V1 didn't help. A per-segment bias would have looked huge but is calibration, not improvement (rule 8).
- Tesla has more segments but no decodable yaw truth (rule 4) — would have silently scored noise.

## Surprise / regression

**V3 regresses on the straight regime** (0.468 → 0.505 deg/s, +0.037). Physical cause: scaling pred by k=1.085 also amplifies the integrator's small straight-line drift, where there is no real signal to gain-match against. A regime-gated gain (apply k only when |δ_road| > 0.005) would dominate V3, but I kept V3 single-knob per rule 11 (same mask across regimes). I did **not** re-derive `a_y_pred = v·ψ̇` for the new yaw — flagged for rule 9; the next ratchet step.

Files: `tools/ablate.py`, `out/variant_ladder.csv`.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleC-m2-agent-03",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-2/agent-03/REPORT.md",
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
