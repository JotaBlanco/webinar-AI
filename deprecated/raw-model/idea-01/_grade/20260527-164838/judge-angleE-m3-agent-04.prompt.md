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

- agent_id: **angleE-m3-agent-04**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-3/agent-04/REPORT.md`

```markdown
# Lateral-Fidelity Triage — webinar-angle-E / module-3 / agent-04

**Platform:** `FORD_MUSTANG_MACH_E_MK1`
**Skill:** `yaw-divergence-triage` (composed with `regime-comparison`)
**Metric:** `RMSE(yaw_rate_pred_rads − yaw_rate_meas_rads)` in rad/s.

## Operating contract

- `yaw_rate_meas_rads` from the Ford `sim.csv` is the measured truth channel.
- `v_mps` and `delta_road_rad` are clamped to measured in KS, by harness contract.
- The lateral residual is the **only** lateral fidelity metric; speed-state agreement is zero by construction and not used.
- Rows: 913,626 across the Mach-E segment set. Regime split: straight 785,093 / steady 106,978 / transient 21,555.

## Variant ladder

| variant | overall | straight | steady | transient | marginal (overall) | attribution |
|---|---:|---:|---:|---:|---:|---|
| V0 raw residual | 0.016127 | 0.008768 | 0.031733 | 0.056797 | — | baseline |
| V1 KS recalibrated (canonical L + per-segment bias) | 0.014693 | 0.004931 | 0.031681 | 0.057296 | **−0.001434** | the only improving step |
| V2 linear ST, prior Cα (openpilot) | 0.016529 | 0.007005 | 0.034497 | 0.062343 | +0.001836 (**regression**) | gain too low — see notes |
| V3 linear ST, fit Cα (L-BFGS-B bounded) | 0.016635 | 0.007000 | 0.034822 | 0.062659 | +0.000106 (**regression**) | optimiser stuck at x0 — see notes |

- Total drop V0→V3: **−0.000508 rad/s** (the ladder ends *worse* than V0).
- Sum of marginal drops: **−0.000508 rad/s** — exact (within 0.0% of total, well inside the 15% reconciliation bound).
- Attribution scheme: strict marginal, fixed order V0→V1→V2→V3.

## Regression flags (honest)

- **V1→V2 (overall +0.001836)** — the steady-state linear-bicycle gain `v·δ / (L·(1+K_us·v²))` underpredicts yaw rate vs the simpler KS `v·tan(δ)/L`. The openpilot prior `C_αf=286.5k, C_αr=355.9k N/rad` is too soft, so `K_us` is large and the predicted yaw rate is biased low. Also, V2 has **no per-segment bias removal** (the helper's bias step lives only in V1), so the gyro DC offset that V1 cancelled is reintroduced.
- **V2→V3 (overall +0.000106)** — V3 fit is degenerate (see below). It returns the starting point `(1.5e5, 1.5e5)` rather than a true minimum. Same missing per-segment bias as V2.

## V3 fit diagnostic — painful absence

The skill's `v3_linear_st_fit` runs L-BFGS-B with bounds `(5e4, 5e5)` and `x0=(1.5e5, 1.5e5)`. Across five sanity-check restarts the optimiser converged with `PGTOL` after **zero** real steps from every starting point:

| `x0` | returned `(C_αf, C_αr)` | loss | message |
|---|---|---:|---|
| (5e4, 5e4) | (5e4, 5e4) | 0.019558 | PGTOL |
| (1.5e5, 1.5e5) | (1.5e5, 1.5e5) | 0.016635 | PGTOL (← reported V3) |
| (2.5e5, 2.5e5) | (2.5e5, 2.5e5) | 0.016312 | PGTOL |
| (3e5, 3.5e5) | (3e5, 3.5e5) | 0.016411 | PGTOL |
| (5e5, 5e5) | (5e5, 5e5) | 0.016316 | PGTOL |

The loss surface is near-flat in the bounded region; finite-difference gradients fall under `pgtol` immediately. `pegged=False` in the skill's pegged-bound check, but for a worse reason than the SKILL.md anticipates: the optimiser never moved. The skill has no gradient-free fallback (Nelder-Mead, differential evolution) — that is the most painful absence.

A wider sweep would put the true minimum *above* the upper bound; V1 (KS+bias) still beats the best linear-ST point.

## Attribution — per-regime contrast (sibling skill)

Composed `regime-comparison/compare.contrast(df, {V0,V1,V2,V3})` on the same regime-tagged DataFrame:

| variant | Δ straight | Δ steady | Δ transient | dominant regime |
|---|---:|---:|---:|---|
| V0 | 0.000000 | 0.000000 | 0.000000 | — |
| V1 | −0.003837 | −0.000051 | +0.000500 | straight |
| V2 | −0.001762 | +0.002764 | +0.005546 | transient |
| V3 | −0.001767 | +0.003089 | +0.005863 | transient |

Read: V1's entire improvement is the straight-line DC-bias cancellation; it leaves cornering essentially untouched (and microregresses transient). V2/V3 partially keep the straight-line win (the gain `v·δ/(L·…)` ≈ `v·tan(δ)/L` for small δ) but lose far more in transient cornering, where the steady-state assumption (zero `δ̇`, zero β̇) doesn't hold.

## Conclusion

- The lateral predictions improve by **−0.001434 rad/s overall RMSE (≈ −8.9%)**, all of which is attributable to **V1: per-segment yaw-gyro bias removal on the canonical KS model.**
- The linear single-track ladder (V2, V3) regresses on this dataset because (a) it drops the bias step and (b) for this vehicle the loss-vs-Cα landscape is too flat for L-BFGS-B to fit. V3 as shipped is the prior in disguise.

## Surprise

Openpilot's stock `C_α` is "too soft" for the Mach-E here, but L-BFGS-B can't tell — the RMSE difference between `1.5e5` and `5e5` is on the order of 3e-4 rad/s, well inside the optimiser's `pgtol`. The honest single-line summary is *"transferring the V1 straight-line bias step into V2/V3 would matter more than re-fitting Cα."*

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleE-m3-agent-04",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-3/agent-04/REPORT.md",
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
