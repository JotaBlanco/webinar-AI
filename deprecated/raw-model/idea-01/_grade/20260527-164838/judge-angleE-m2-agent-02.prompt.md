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

- agent_id: **angleE-m2-agent-02**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-2/agent-02/REPORT.md`

```markdown
# REPORT — lateral-fidelity workflow (workshop scaffold S2)

## Platform and contract

- Platform scored: **FORD_MUSTANG_MACH_E_MK1** (Ford Mustang Mach-E MK1, 315 segments, 913,626 rows).
- `yaw_rate_meas_rads` is measured truth (rlog IMU, Ford-only).
- Speed `v` and steering `δ` are **clamped** to measured under the speed-known operating contract (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). The lateral residual `yaw_rate_resid_rads = yaw_rate_pred − yaw_rate_meas` is the sole metric. No unclamping was attempted.

## Variant ladder

| variant | overall | straight | steady | transient |
|---|---:|---:|---:|---:|
| V0 (baseline KS)               | 0.01613 | 0.00877 | 0.03173 | 0.05680 |
| V1 (KS recalib + per-seg bias) | 0.01469 | 0.00493 | 0.03168 | 0.05730 |
| V2 (Linear ST, prior Cα)       | 0.01653 | 0.00701 | 0.03450 | 0.06234 |
| V3 (Linear ST, fit Cα)         | 0.01663 | 0.00700 | 0.03482 | 0.06266 |

V3 fit result: `C_alpha_f = 1.50e5`, `C_alpha_r = 1.50e5` (= x0), `pegged = False`. L-BFGS-B did not move from initialisation, indicating effectively zero gradient at x0 under the clamped formulation — V3 is not a meaningful refinement of V2 in this run.

## Attribution

Marginal change in **overall** RMSE (negative = improvement):

- V0 → V1 marginal drop: **−0.00144** (−8.9%). Almost entirely from the *straight* regime (0.00877 → 0.00493, −0.00384). The per-segment yaw-gyro bias term is doing nearly all of the V1 work; KS re-derivation from canonical `L` is a small contributor.
- V1 → V2 marginal drop: **+0.00184** (regression of 12.5%). Worsens every regime.
- V2 → V3 marginal drop: **+0.00011** (further marginal regression; fit did not move).
- Sum of marginals: −0.00144 + 0.00184 + 0.00011 = **+0.00051**.
- Total V0 → V3: 0.01663 − 0.01613 = **+0.00050**.
- Sum-of-marginals vs total: agree to within rounding (well within 15%). ✓

## Regressions and physical reasons

- **V2 and V3 regress past V0 overall, and on every regime row.** Per the workflow contract, V3 hitting the upper bound is the named regression flag; here V3 did *not* peg, but it also did not improve over V2, and both sit above V0. I am flagging V2/V3 as a structural regression of the Linear-ST step on this platform.
- Most likely physical causes (workflow does not let me confirm, only hypothesise):
  - The understeer-gradient term `K_us = m·(l_r·C_r − l_f·C_f) / (L²·C_f·C_r)` on the Mach-E is small but **negative-leaning under the openpilot prior** (l_r > l_f, C_r > C_f), pushing ψ̇ in the wrong direction relative to measured yaw under steady cornering — visible as worsening *steady* and *transient* rows.
  - V3's L-BFGS-B starting at (1.5e5, 1.5e5) sat in a flat region of the loss surface — no descent direction found. The fitter is under-specified for clamped-`v`/`δ` data where ψ̇ ≈ (v/L)·tan δ already explains most variance, and the Cα-dependent correction is small relative to gyro bias.
  - V1's straight-regime win confirms a non-trivial **per-segment gyro-bias floor** in the rlog IMU data; until that bias is removed first, ST can only correct around a biased target.

## Notes

- **Tool patch (deviation, recorded):** `tools/step4_run_st_upgrade.py` was broken on first run — it called `P["L"]` on a `MachEST` frozen-dataclass, raising `TypeError: 'MachEST' object is not subscriptable`. I added a minimal `_Bridge` wrapper inside the tool to translate `P["k"]` to `getattr(P, "k")`, with no other change. This is a tool-mechanics fix, not a model change.
- **Workflow honoured:** Steps 1–5 run in order, with the documented flags. No catalogue, no skill, no eval was invoked. No V4 invented. Platform not switched.
- **What I'd want next (out of scope here):** a per-segment audit of `bias` magnitude (is the gyro-bias drive-dependent or vehicle-dependent?); a sign-check on the openpilot Cα prior vs. the road-wheel convention this pipeline uses; and a way to score ST *after* the V1 bias removal, since the current ladder applies bias only inside V1 and discards it for V2/V3 — that ordering may itself be why V2/V3 regress.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleE-m2-agent-02",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-2/agent-02/REPORT.md",
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
