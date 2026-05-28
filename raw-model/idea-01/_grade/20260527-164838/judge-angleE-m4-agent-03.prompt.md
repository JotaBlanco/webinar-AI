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

- agent_id: **angleE-m4-agent-03**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-4/agent-03/REPORT.md`

```markdown
# REPORT.md — module-4/agent-03 (RPI loop, angle-E)

## Headline
- Platform: **FORD_MUSTANG_MACH_E_MK1** (315 segments, 913 626 rows).
- Net V0→V3 RMSE change: **0.01613 → 0.01663 rad/s (−0.0005, i.e. worse).** V1 is the only variant that improves the metric; V2 and V3 regress.

## Operating contract
- Truth channel: `yaw_rate_meas_rads` (measured, present on Ford only).
- Inputs `v_mps` and `delta_road_rad` are **clamped to measured** (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Speed-state agreement is zero by construction and not the metric.
- Lateral metric: `RMSE(yaw_rate_resid_rads)` overall and per regime (`|δ| < 0.01` straight; `≥0.01 & |dδ/dt| < 0.05` steady; else transient, dt=0.02 s).

## Variant ladder

| Variant | RMSE overall | RMSE straight | RMSE steady | RMSE transient | ΔRMSE (marginal) | Attribution note |
|---|---|---|---|---|---|---|
| V0 baseline (sim.csv as-is) | 0.01613 | 0.00877 | 0.03173 | 0.05680 | — | reference |
| V1 KS recalibrated + per-segment straight-line bias | 0.01469 | 0.00493 | 0.03168 | 0.05730 | **+0.00143** | bias subtraction cuts straight RMSE 44 %; cornering unchanged |
| V2 Linear ST, openpilot prior C_α | 0.01653 | 0.00701 | 0.03450 | 0.06234 | **−0.00184** | ST gain damps yaw vs KS but the prior C_α implies more understeer than the tyre exhibits → cornering RMSE rises |
| V3 Linear ST, fitted C_α | 0.01663 | 0.00700 | 0.03482 | 0.06266 | **−0.00011** | fit returned C_αf = C_αr = 1.50e5 (= L-BFGS-B start point, **not** pegged at 5e5) — see dissent |

## Attribution accounting
- Scheme: strict marginal, fixed order V0→V1→V2→V3. `ΔRMSE_i = RMSE(V_{i-1}) − RMSE(V_i)`.
- Total V0→V3: **−0.00051**. Sum of marginals: **−0.00051**. Reconcile gap **0.0 %** (well inside 15 %).
- V1 contributes +0.00143 (yaw-gyro bias removed on straights — Phase-1's "Lightning has a non-zero mean residual" finding generalised; Mach-E also carries a small per-segment offset).
- V2 contributes **−0.00184** (regression) — biggest single change in the ladder, and the wrong direction.
- V3 contributes **−0.00011** (regression) — within numerical noise of V2.

### Regime contrast (sibling skill, deltas vs V0 RMSE; same regime mask)

| variant | Δ straight | Δ steady | Δ transient | dominant regime |
|---|---|---|---|---|
| V1 | −0.00384 | −0.00005 | +0.00050 | straight |
| V2 | −0.00176 | +0.00276 | +0.00555 | transient |
| V3 | −0.00177 | +0.00309 | +0.00586 | transient |

V1 lives entirely on straights (bias term). V2 and V3 lose all their straight-line gain back in cornering, then some — transient is where the ST prior misbehaves.

## Regression flags
- **V2 vs V1 — physical cause.** The openpilot prior C_αf=286 551 / C_αr=355 912 N/rad implies a stiff understeering linear bicycle. On these segments the simple `tan(δ)·v/L` (V1) is closer to truth in steady cornering than the gain-shaped ST. Switching to V2 imports the wrong understeer assumption.
- **V3 fit did not escape start point** — `C_αf = C_αr = 1.50e5` is exactly the L-BFGS-B initial guess in `triage.v3_linear_st_fit`. The pegged-bound check returned `pegged=False` correctly (no parameter at 5e5), but the fit is still a non-fit. Cause: the loss surface contains a singular ridge where `1 + K_us·v² = 0` (denominator flips sign at high v / low C_αr); RMSE jumps to ~10⁰–10² there, blocking the gradient. This is a skill bug surfaced by Phase 3.

## What each phase bought (RPI evidence)
- **Phase 1 (research)** surfaced two facts that drove every later decision: (a) cornering carries 6× the straight-line residual, so straight-only fixes can't help much in absolute terms, and (b) Lightning has a non-zero mean residual where Mach-E doesn't — that pushed the platform choice and pre-justified V1's bias term.
- **Phase 2 (plan)** committed to fixed marginal attribution V0→V3 *before* seeing any V2/V3 numbers. Without that lock the temptation in Phase 3 would have been to drop V2 once it regressed; instead the regression is the result.
- **Phase 3 (implement)** is where the locked plan paid off: V2 and V3 came back red, but because the ladder was fixed they're reported as honest regressions, not silently dropped.

## Plan dissent
- The locked plan said "V3 — Linear ST with fitted C_αf, C_αr". V3 as implemented in `triage.v3_linear_st_fit` does *not* actually fit on this dataset — L-BFGS-B can't cross the `1+K_us·v²=0` singular ridge from the (1.5e5, 1.5e5) start, so it returns the start point. A coarse grid run in Phase 3 (not patched into the locked plan) shows the actual loss minimum sits near (3.5e5, 3.5e5) at RMSE ≈ 0.01628, i.e. essentially indistinguishable from the prior (0.01653) and still worse than V1 (0.01469).
- Had the plan permitted, the right Phase-3 move would be either (a) replace L-BFGS-B with a global / differential-evolution search inside C_BOUNDS, or (b) constrain the search to `K_us > −1/v_max²` to keep the denominator positive. Neither would change the headline — V1 would still be the only improvement — but it would make V3 a real fit instead of a no-op.
- I did **not** rerun V3 with a global optimiser in the reported numbers, in keeping with the RPI contract that Phase 3 executes the locked plan.

## Bottom line
- The "make the lateral prediction better" answer for Mach-E is **V1 only**, with a +0.00143 rad/s overall RMSE drop (8.9 %), concentrated entirely on straights.
- V2 and V3 should not be shipped on this segment set: the openpilot ST prior is the wrong shape for these tyres, and the V3 optimiser silently fails to disagree with it.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleE-m4-agent-03",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-4/agent-03/REPORT.md",
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
