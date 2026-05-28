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

- agent_id: **angleE-m4-agent-05**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-4/agent-05/REPORT.md`

```markdown
# REPORT.md — webinar-angle-E / module-4 / agent-05

## Platform
`FORD_MUSTANG_MACH_E_MK1` (315 segments, 913,626 samples at 50 Hz).

## Contract
- `yaw_rate_meas_rads` is the measured truth channel.
- `v_mps` and `delta_road_rad` are **clamped to measured**; speed-state agreement is zero by construction and is **not** the metric.
- Metric: `RMSE(yaw_rate_resid_rads)` overall and per regime (straight / steady / transient) using the skill's `triage.regime_mask`.

## Variant ladder

| variant | description | overall RMSE | straight | steady | transient | marginal Δ overall |
|---|---|---|---|---|---|---|
| V0 | baseline `yaw_rate_resid_rads` column as-is | 0.01613 | 0.00877 | 0.03173 | 0.05680 | — |
| V1 | KS recalibrated, canonical L, per-segment gyro-bias removal | **0.01469** | **0.00493** | 0.03168 | 0.05730 | +0.00143 (improve) |
| V2 | Linear ST, prior `C_αf=286551`, `C_αr=355912` N/rad, `v_min=2 m/s` KS fallback | 0.01653 | 0.00701 | 0.03450 | 0.06234 | −0.00184 (regression) |
| V3 | Linear ST, fitted `C_αf=150000`, `C_αr=150000` N/rad (bounds 5e4–5e5, not pegged) | 0.01663 | 0.00700 | 0.03482 | 0.06266 | −0.00011 (regression) |

(Per-regime numbers are RMSE in rad/s. "Marginal Δ overall" = `RMSE(V_{i-1}) − RMSE(V_i)`; positive = improvement.)

## Attribution

- **Accounting scheme:** strict marginal, fixed order V0 → V1 → V2 → V3 (telescoping). Sum of marginals = `+0.00143 − 0.00184 − 0.00011 = −0.00051 rad/s`, exactly equal to `RMSE(V0) − RMSE(V3)` (ratio 1.000, within the 15% tolerance).
- **Net effect of the ladder:** the whole ladder makes things *worse* overall (−0.00051) because V2 and V3 regress more than V1 improves.
- **Where V1 earned its delta:** entirely on the straight regime (−0.00384 rad/s). Physically this is removing the per-segment yaw-gyro DC bias — straight-line samples should have `ψ̇ ≈ 0` and the bias was ~+0.012 rad/s on the first segment alone.
- **Per-regime contrast (from `regime-comparison/compare.contrast`):**

| variant | Δ straight | Δ steady | Δ transient | dominant regime |
|---|---|---|---|---|
| V1 | −0.00384 | −0.00005 | +0.00050 | straight |
| V2 | −0.00176 | +0.00276 | +0.00555 | transient |
| V3 | −0.00177 | +0.00309 | +0.00586 | transient |

(Negative = RMSE went down vs V0 = improvement. Positive = regression.)

## Regression flags

- **V2 vs V1, steady regime:** +0.00282 rad/s. Physical cause: the Linear ST steady-state gain `v·δ / (L·(1+K_us·v²))` assumes linear tyres at small slip; the Mach-E `C_α` prior values produce a `K_us` that *under-rotates* the model relative to KS on the data's actual slip levels, so the residual sign reverses on most steady samples.
- **V2 vs V1, transient regime:** +0.00555 rad/s. Physical cause expected: Linear ST is a *steady-state* model; transients excite yaw-rate dynamics (`I_z ψ̈`) that the model can't represent. Swapping KS for Linear ST throws away KS's instantaneous geometric response without buying any transient physics back.
- **V3 vs V2:** essentially flat (−0.00011). The optimizer (`scipy.optimize.minimize`, L-BFGS-B, initial guess `(1.5e5, 1.5e5)`) returned exactly the initial point with no bound peg — flat gradient region; see Plan Dissent.
- **V1 vs V0, transient regime:** +0.00050 (mild regression). Physical cause: V1 KS prediction uses canonical L which may differ slightly from the (unknown) baseline pipeline's effective L; the bias term is calibrated on straight samples so it doesn't compensate the transient mismatch.

## Phase attribution (what each RPI phase surfaced)

- **Phase 1 (Research):** non-zero straight-line mean residual (~+0.012 rad/s) — predicted V1 would dominate before any V1 code ran. Noted Lightning's stationary stretches as a `v_min` risk; that fed the platform choice in Phase 2.
- **Phase 2 (Plan):** committed to one platform (Mach-E) and to the V0–V3 ladder, with explicit "out of scope" for V4 residual learner and Lightning. Locked the strict marginal accounting scheme and the report shape before seeing any V2/V3 numbers.
- **Phase 3 (Implement):** numerical V3-pegged-initial-guess discovered (not the upper bound — the initial point). Per RPI lock-in, the locked-plan V3 numbers stand; dissent below.

## Plan dissent

The skill's `triage.v3_linear_st_fit` uses L-BFGS-B with finite-difference gradients from initial guess `(1.5e5, 1.5e5)`. On this data the loss surface is shallow there and L-BFGS-B returns the initial guess unchanged (`fit_info = {C_αf=150000, C_αr=150000, pegged=False}`). An out-of-band Nelder-Mead probe with the same loss converged to `(C_αf, C_αr) ≈ (1.62e5, 1.42e5)` with RMSE ≈ 0.01628 — still worse than V1's 0.01469, so the *conclusion* (Linear-ST family is structurally wrong for transients on this data) is robust, but the V3 RMSE reported in the table above is **not** the true family minimum. A future run should either change the V3 optimizer in the skill or document this behaviour.

A secondary skill-body issue: `triage._load_params` does `dict["L"]`-style access, but `parameters.PARAM_BY_PLATFORM` returns a dataclass (`MachEST(L=2.984, ...)`). Patched in the driver via a `dataclasses.fields()` adapter; not modified in the skill source.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleE-m4-agent-05",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-4/agent-05/REPORT.md",
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
