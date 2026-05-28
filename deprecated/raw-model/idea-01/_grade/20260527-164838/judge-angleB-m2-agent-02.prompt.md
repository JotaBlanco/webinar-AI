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

- agent_id: **angleB-m2-agent-02**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-2/agent-02/REPORT.md`

```markdown
# Module-2 / agent-02 (angle-B) — Lateral fidelity, Ford Mustang Mach-E (MK1)

**Platform scored:** `FORD_MUSTANG_MACH_E_MK1`, 80 segments (first 80 alphabetically), pre-generated `sim.csv`.
**Truth channel:** `yaw_rate_meas_rads` — measured from the Ford CAN bus via `adapter_ford_rlog.py` (opendbc `ford_lincoln_base_pt`). Not self-consistency, not predicted.
**Clamped (inputs):** `v` (`clamp_v_to_measured=True`) and `δ` (`clamp_delta_to_measured=True`).
**Predicted (under test):** `yaw_rate_pred_rads`; residual = `pred − meas`.
**Regime mask (identical across all variants):**
- straight: `|ψ̇_meas| < 0.02 rad/s`
- transient: `|ψ̇_meas| ≥ 0.02` ∧ rolling-25-sample std of `ψ̇_meas` > 0.02
- steady: `|ψ̇_meas| ≥ 0.02` ∧ not transient

## Variant ladder

| Variant | Change | RMSE all | straight | steady | transient | Marginal drop (all) |
|---|---|---:|---:|---:|---:|---:|
| V0 | baseline, `yaw_rate_resid_rads` as-shipped | 0.01190 | 0.00778 | 0.01767 | 0.05521 | — |
| V1 | + per-segment mean-bias removal | 0.00992 | 0.00412 | 0.01647 | 0.05489 | -0.00197 |
| V2 | V1 + linear ST steady-state gain `v·δ/(L·(1+K_us·v²))` using shipped C_α | 0.01145 | 0.00364 | 0.01995 | 0.06432 | +0.00153 (regression) |
| V3 | V1 + first-order steering lag (τ = 0.10 s) on `δ_road`, KS kinematics | 0.00924 | 0.00388 | 0.01594 | 0.04858 | -0.00221 |
| V4 | V3 + global scalar gain k=1.0277 fitted on first 40 segs | 0.00864 | 0.00394 | 0.01471 | 0.04462 | -0.00060 |

**Accounting:** marginal/sequential. Sum of marginals = -0.00325 rad/s; total V0→V4 = -0.00325 rad/s; exact.

## Regression analysis (V2)

Applying the linear ST yaw-rate gain with shipped `C_αf=286,551, C_αr=355,912 N/rad` yields `K_us=5.62e-4`, i.e. a gain factor ~0.82 at v=20 m/s. An empirical least-squares fit of `ψ̇_meas` against KS prediction `v·tan(δ)/L` returns gain ≈ **1.04** — the data wants slightly *more* yaw rate than KS, not less. The shipped cornering-stiffness prior overstates understeer for this tyre/road combination. Until C_α is refit, V2 is a regression and V3/V4 keep KS kinematics.

## Headline

**Yaw-rate RMSE 0.01190 → 0.00864 rad/s (-27.4%) across 80-segment Mach-E set, mask locked.** Biggest contributors: steering-lag (V3, 0.0022 rad/s) and bias removal (V1, 0.0020 rad/s). ST-with-shipped-priors hurt; a global gain on top of lag bought another 0.0006.

## What is not fixed

Transient-cornering residual still ~0.045 rad/s — five times the straight-line floor. KS-with-lag can't capture tyre relaxation length or weight transfer; closing requires ST with calibrated C_α or Pacejka.

## Painful absence

A **skills/ or evals/ harness** — no scaffolded "run the ladder, print the regime-bucketed RMSE" loop. Wrote it from scratch under a 15-min budget while every turn re-paid the full AGENTS.md + CLAUDE.md context.

## Rule-prevented near-misses

- Trap #2 (don't unclamp v/δ) — considered relaxing δ-clamp to let the steering integrator absorb the lag rather than pre-filtering δ; treated τ as input transform instead.

## Most surprising

The shipped `C_αf, C_αr` priors push the ST model the **wrong way** on this fleet — KS overpredicts yaw rate slightly, but linearised ST with priors *under*predicts much more. Recalibrating C_α matters more than upgrading model order. The fidelity-ladder rung is not the bottleneck; the parameter prior is.

Files: `tools/analyze.py`, `out/results.txt`.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleB-m2-agent-02",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-2/agent-02/REPORT.md",
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
