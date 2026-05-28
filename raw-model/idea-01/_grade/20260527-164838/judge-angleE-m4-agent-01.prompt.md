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

- agent_id: **angleE-m4-agent-01**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-4/agent-01/REPORT.md`

```markdown
# REPORT.md — webinar-angle-E / module-4 / agent-01

## 1. Platform & operating contract

- Platform: **`FORD_MUSTANG_MACH_E_MK1`** (skill default; 914,626 rows across 315 segments).
- `yaw_rate_meas_rads` is the measured truth channel (present on both Ford platforms, absent on Tesla).
- KS runs with `clamp_v_to_measured=True`, `clamp_delta_to_measured=True`. Speed-state agreement is zero by construction and is not the metric. `v` and `δ_road` are inputs; `yaw_rate_resid_rads = pred − meas` is the only metric.

## 2. Variant ladder (per-regime RMSE, rad/s)

| variant | overall | straight | steady | transient | marginal Δ overall | notes |
|---|---|---|---|---|---|---|
| V0 — baseline (column as-is) | 0.01613 | 0.00877 | 0.03173 | 0.05680 | — | from `yaw_rate_resid_rads` in `sim.csv` |
| V1 — KS recalib + per-segment straight-line bias | **0.01469** | **0.00493** | 0.03168 | 0.05730 | -0.00143 (-8.9%) | bias removal almost entirely on straights |
| V2 — Linear ST, prior C_α (low-v KS fallback) | 0.01653 | 0.00701 | 0.03450 | 0.06234 | +0.00184 (regression) | regresses all three regimes vs V1 |
| V3 — Linear ST, fitted C_α | 0.01663 | 0.00700 | 0.03482 | 0.06266 | +0.00011 (regression) | fit degenerate (see dissent) |

Net V0→V3: **+0.00051 rad/s overall (got worse)**. Net V0→V1 (best): **-0.00143 rad/s (-8.9%)**.

## 3. Attribution

- Scheme: strict marginal, fixed order V0→V1→V2→V3. Marginal_i = RMSE(V_{i-1}) − RMSE(V_i).
- Marginal drops: V1 +0.00143, V2 −0.00184, V3 −0.00011. Sum = −0.00051. Total V0−V3 = −0.00051. **Mismatch 0.0%** (trivially within 15%; the check is by construction for overall RMSE).
- Per-regime contrast (sibling skill `regime-comparison`, negative = improvement vs V0):

| variant | Δ straight | Δ steady | Δ transient | dominant regime |
|---|---|---|---|---|
| V1 | -0.00384 | -0.00005 | +0.00050 | straight |
| V2 | -0.00176 | +0.00276 | +0.00555 | transient (regression) |
| V3 | -0.00177 | +0.00309 | +0.00586 | transient (regression) |

- V1 earns its entire win on the **straight** regime (per-segment yaw-gyro bias removal).
- V2 and V3 *help* on straights (smaller than V1's straight-line help) but *hurt* on steady and transient — they regress where the modelling change was supposed to pay off.

## 4. Regression flags

- **V2 vs V1, all regimes.** Linear-ST with openpilot prior C_α (286,551 / 355,912 N/rad) under-yaws relative to measured at the Mach-E's steering levels. Physical reason: the prior is generic, and tan(δ) → δ approximation drops nonlinear high-δ contribution that KS retains; on transients the linear model also misses lag.
- **V3 vs V2, all regimes.** Marginal further regression of ≈+1e-4 rad/s overall.
- **V3 fit is degenerate** — see Plan dissent. Treat V3 numbers as "model class V2 with optimiser confirmation", not "calibrated".

## 5. RPI provenance (which phase surfaced which decision)

- **Phase 1 (research.md):** flagged Lightning's 17% low-v share and persistent residual mean (-3.6e-3), which is why Mach-E was chosen in Phase 2 rather than blindly defaulted. Also surfaced the transient-vs-straight RMSE ratio (~6×) before any modelling.
- **Phase 2 (plan.md):** locked attribution scheme + 15% sum-check + out-of-scope list (V4 residual learner, nonlinear Pacejka, per-segment C_α fit, unclamping). The pre-commit to "report regressions honestly" made it natural to flag V2/V3 as regressions in Phase 3 instead of burying them.
- **Phase 3 (this report):** discovered the V3 optimiser degeneracy — the L-BFGS-B fit did not move from its `(1.5e5, 1.5e5)` initialisation. Not surfaceable in Phase 1 or 2.
- Net: the RPI split mostly bought *honesty about regressions*; it did not surface or repair the V3 fit degeneracy.

## 6. Plan dissent

- V3 L-BFGS-B returned exactly the init `(C_αf, C_αr) = (1.5e5, 1.5e5)` with `pegged=False`. The fit is degenerate — either the loss is flat at init scale or the finite-difference gradient underflowed. Per the AGENTS.md RPI contract I executed the locked plan as written and did **not** swap optimiser, add random restarts, or rescale parameters mid-Phase-3. A future run should:
  - normalise C_α by 1e5 before passing to L-BFGS-B, or
  - use a global method (Nelder–Mead with random restarts, or differential_evolution) over the bounded box, and
  - separately fit per-segment vs global to test whether the regression is a model-class issue or a calibration issue.
- Recommendation independent of dissent: **ship V1**, mothball V2/V3 until a non-degenerate fit can be produced, and consider a residual learner (out-of-skill V4) for the transient regime where physics-based models all degrade.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleE-m4-agent-01",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-4/agent-01/REPORT.md",
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
