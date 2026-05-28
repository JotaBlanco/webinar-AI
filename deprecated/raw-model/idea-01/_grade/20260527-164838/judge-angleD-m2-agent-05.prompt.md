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

- agent_id: **angleD-m2-agent-05**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-2/agent-05/REPORT.md`

```markdown
# REPORT — webinar-angle-D / module-2 / agent-05

**Task:** lateral-fidelity-challenge (improve lateral / yaw-rate prediction of the KS model on Ford segments, attribute the gain).
**Skill:** `lateral-fidelity-triage` v0.1 (first crystallisation).

## Scoring substrate

- **Platform:** `FORD_MUSTANG_MACH_E_MK1` (Mach-E). Per the skill's "Truth-channel discovery" rule, Mach-E is the default Ford pass; both Fords carry decoded IMU truth, Tesla does not.
- **Truth channel:** `yaw_rate_meas_rads` — **measured** (Ford IMU, decoded from party DBC in the rlog). Not a prediction.
- **Operating contract:** `clamp_v_to_measured=True`, `clamp_delta_to_measured=True`. `v` and `δ_road` are inputs; the only thing under test is the lateral-state map `(v, δ_road) → ψ̇`.
- **Segments:** first 20 Mach-E `sim.csv` files (sorted, deterministic) → **57,979 rows**.
- **Sign check:** `corr(δ_road, ψ̇_meas)` on cornering rows (|δ|>0.02): **+0.943** → sign convention is correct, no flip needed.

## Variant ladder

All numbers are RMSE of `(ψ̇_pred − ψ̇_meas)` in rad/s. Per-segment straight-line gyro bias is subtracted on V1/V2/V3 per the skill's V1 rule.

| Variant | Overall | Straight | Steady | Transient | Δ vs prev | % vs prev |
|---|---:|---:|---:|---:|---:|---:|
| V0  baseline (as-shipped `yaw_rate_resid_rads`)            | 0.01575 | 0.01095 | 0.04411 | 0.06379 | —          | —         |
| V1  KS recal (`L=2.875`) + per-seg straight-line bias      | 0.01368 | 0.00662 | 0.04522 | 0.06738 | −0.00207   | **−13.2%** |
| V2  Linear-ST, prior C_α (286.5k / 355.9k)                 | 0.01606 | 0.00351 | 0.06072 | 0.08514 | +0.00238   | +17.4%    |
| V3  Linear-ST, fit C_α (multi-start; 3.0e5 / 3.0e5)        | 0.01581 | 0.00368 | 0.05953 | 0.08367 | −0.00025   | −1.5%     |
| V4  V3 + Ridge residual learner (LOO over segments)        | 0.01499 | 0.00376 | 0.05453 | 0.08119 | −0.00082   | −5.2%     |

**End-to-end:** V0 → V4 = **0.01575 → 0.01499 rad/s, −4.8% RMSE.**

## Attribution

| Step | Mechanism | Where it helps | Where it hurts | Δ overall RMSE |
|---|---|---|---|---:|
| V1 | canonical wheelbase + per-segment yaw-gyro bias removal | straight-line (×0.60) | cornering very slightly worse (geometric KS still no slip) | **−13.2%** |
| V2 | linear-ST steady-state gain replaces tan(δ) geometry | straight-line (×0.53 vs V1) | steady (+34%) and transient (+26%) — linear-ST under-predicts cornering yaw on Mach-E | **+17.4%** |
| V3 | C_α fit on whole segment set (multi-start; helper as-shipped is broken — see below) | marginal vs V2 | barely moves the needle: priors were close to the symmetric-fit optimum | **−1.5%** |
| V4 | Ridge residual learner over `[v, |a_y|, |δ|, sign(δ̇)]`, LOO-CV | steady (−8.4% vs V3) and transient (−3.0% vs V3) | straight-line (+2%) — learner over-corrects when error is already small | **−5.2%** |

Net contributions to the −0.000754 rad/s overall improvement:
- V1 (KS recal + bias): **−0.00207** → contributes **+274%** of the net (i.e. it does all the work and then some).
- V2 + V3 combined: **+0.00214** (net regression).
- V4: **−0.00082** (claws back roughly what V2 cost on cornering).

The skill's ladder, taken end-to-end on Mach-E, is **front-loaded**: nearly all the win is in V1; V2/V3 trade straight-line accuracy for cornering accuracy in the wrong direction; V4 partially repairs that trade.

## Findings on the skill itself (v0.1, first crystallisation)

1. **`triage.fit_c_alpha` is broken in practice.** It runs a single L-BFGS-B from `x0=(1.5e5, 1.5e5)` on a non-convex loss with cliffs where `1 + K_us·v²` crosses zero. The optimizer returns x0 unchanged. A 5×5 grid multi-start finds the actual minimum at (3.0e5, 3.0e5), RMSE 0.01735 vs single-start 0.02. **Patch needed:** multi-start, or random-restart, or trust-region.
2. **No regime-weighted fit.** The C_α fit minimises overall RMSE, dominated by straight-line samples where the linear-ST gain is nearly insensitive to C_α. A cornering-only fit would be the obvious v0.2 patch.
3. **No KS↔ST handoff rule.** Skill says "below `v_min`, fall back to KS" — fine — but no rule for when KS is better than ST *above* `v_min`. On this data, KS+bias (V1) **beats** linear-ST (V2/V3) on cornering. The skill walks the ladder upward by definition; the operator needs a "stop here" criterion.
4. **No held-out segments.** V0–V3 are all fit-and-score on the same 20 segments. Only V4 has a LOO-CV protocol. A v0.2 patch should mandate a train/eval split for the C_α fit too.
5. **Attribution is per-step, not orthogonal.** The table above reports `Δ overall RMSE` between consecutive variants. That's what the skill prescribes, but it's order-dependent: V3 looks weak because V2 already moved the needle the wrong way. Shapley-style or all-subsets attribution would be more informative.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleD-m2-agent-05",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-2/agent-05/REPORT.md",
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
