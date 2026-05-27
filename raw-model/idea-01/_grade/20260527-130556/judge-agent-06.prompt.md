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

- agent_id: **agent-06**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-06/REPORT.md`

```markdown
# Lateral Prediction Improvement Report — Agent 06

## 1. Headline number

**Primary metric: yaw-rate RMSE across 520 Ford segments (1.36 M samples at 50 Hz), in-motion (v > 2 m/s) only.**

- **Baseline KS** (`ψ̇ = (v/L)·tan(δ)` from existing `sim.csv` columns): **0.01431 rad/s**
- **Final ladder (v4)**: **0.00999 rad/s** — a **30.2 % reduction**.

Secondary metric (lateral acceleration, `a_y = v·ψ̇`):
- Baseline: **0.386 m/s²** → Final: **0.228 m/s²** — a **40.9 % reduction**.

## 2. What I implemented (sequential ladder)

- **v1_bias** — Per-segment steering-zero offset: median `δ_road` during straight running (|ψ̇|<0.02, |a_y|<0.3, v>8) subtracted before predicting. Removes the steering-sensor zero-point drift each segment carries.
- **v2_understeer** — Steady-state linearised single-track: `ψ̇ = v·tan(δ)/(L + K_us·v²)` where `K_us = (m/L)(l_r/C_f − l_f/C_r)` is computed from the openpilot-canonical mass / CG / tire-stiffness parameters in `parameters.py`. Same model, just one more physically-grounded term.
- **v3_lag** — First-order steering lag on `δ` with τ = 0.05 s (selected by grid sweep in `tools/tune.py`), modelling EPS rack + tire relaxation delay.
- **v4_per_platform_kus** — Per-platform scaling of `K_us` from the grid sweep: Mach-E ×0.5, F-150 Lightning ×3.0 (matches data: the truck understeers far more than its carParams stiffness suggests).

## 3. Attribution — sequential cumulative ladder

**Scheme:** sequential cumulative deltas. Each rung is added on top of the previous; reported `Δ` = RMSE_prev − RMSE_this. "Share" = Δ / (RMSE_baseline − RMSE_final) × 100 %.

| Rung | RMSE yaw (rad/s) | Δ | Share of total yaw-improvement |
|---|---|---|---|
| baseline | 0.01431 | — | — |
| + v1_bias | 0.01368 | 0.00063 | **14.6 %** |
| + v2_understeer | 0.01171 | 0.00197 | **45.6 %** |
| + v3_lag (τ=0.05 s) | 0.01128 | 0.00043 | **10.0 %** |
| + v4_per_platform K_us | 0.00999 | 0.00129 | **29.8 %** |

For lateral accel: v2 dominates (~77 %), v3_lag is neutral-to-slightly-negative (−0.4 %), v4 contributes ~8.7 %, v1 contributes ~14.5 %.

**Note on ordering bias:** sequential attribution depends on rung order. The single biggest individual lever is v2 (understeer term, ~45–77 % of total), and v4 (data-driven retuning of `K_us`) is second. v1 and v3 are real but minor.

## 4. Surprises

- **Two F-150 segments had RMSE ≈ 115 m/s²** because the vehicle was stationary the entire segment (v=0, δ constant) but the IMU still registered ±2 m/s² of lateral acceleration (parking-lot bumps / road grade). These two segments alone made baseline a_y RMSE jump from ~0.4 to ~7. **Added a v > 2 m/s mask** in scoring; not gold-plating, the model is correctly predicting zero, it's the comparison that's nonsensical.
- **The F-150 Lightning needs `K_us` ~3× larger than its carParams-derived value.** Implies the openpilot stiffness numbers for the truck (`C_αf=378k, C_αr=470k`) are over-estimated for its real on-road tire/load combination — it actually understeers harder. The Mach-E goes the other way (wants 0.5×, i.e. less understeer than the prior).
- **Steady-state understeer alone halves the yaw error.** I expected steering lag and bias removal to matter more — the dominant baseline error is just that pure-kinematic KS pretends tires are infinitely stiff, which over-predicts yaw rate at higher speed.
- **Median steering bias is exactly 0** across segments; the carParams calibration is excellent. Only a long tail of segments has non-trivial bias, so v1's contribution comes from those.

## 5. Limitations

- **Tesla segments unused.** 1025 Tesla CSVs exist but lack truth channels (no decoded IMU on Tesla rlogs per the adapter docstring). All scoring is Ford-only.
- **No held-out test set.** v3_lag (τ) and v4 (K_us scales) were tuned on the same segments they're evaluated on — slight optimistic bias. With 520 segments a k-fold split would be straightforward but I didn't budget for it.
- **Sequential attribution is order-dependent.** Shapley-style symmetric attribution would be more rigorous; for 4 factors that's 2⁴=16 fits, doable but I didn't run it.
- **The model is still pure-kinematic + steady-state correction.** A real dynamic single-track (transient `β̇`, `ψ̈`) would likely capture the remaining 0.010 rad/s, especially at high yaw transients. Didn't build it.
- **Couldn't (by contract) read** `webinar-angle-*/modulo-*/` prior solutions, `webinar-00/`, or sibling agent folders. No blocked tool calls — relied on self-restraint.
- **No `Write` block hit** — all my writes were to `tools/` and `out/`, not `*report*.md`.

## Files produced

- `tools/score.py` — main scorer + ladder
- `tools/tune.py` — τ × K_us grid sweep
- `out/summary.json` — final RMSE + attribution table
- `out/per_segment.csv` — per-segment RMSE for every variant
- `out/tune.json` — full grid-search results

```
ISOLATION_REPORT:
read_outside_allowed: []
attempted_blocked: []
shared_dir_writes: []
notes: "Filtered out v<2 m/s samples to suppress parked-vehicle a_y artefacts (two F-150 segments otherwise dominated RMSE). Hyperparameters tau and K_us scales were fit on the full set without a holdout; slight optimistic bias expected on v3/v4 rungs."
```

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "agent-06",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-06/REPORT.md",
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
- `comparable_to_canonical` — for idea-01, "canonical" means a *measured* yaw-rate truth channel on Ford. Agent-01-style fabricated proxies on Tesla → FALSE.
- `attribution_breakdown` — pick one scheme per agent; the agent's primary scheme if multiple are reported (sequential takes precedence over Shapley when both are present and the agent narrates the sequential one). Use the agent's own variant names verbatim — do not rename or normalise across agents.

Notes on `honesty_flags`:
- `named_data_gap_or_missing_truth_channel`: TRUE if the agent explicitly says they could not access a needed source, or that a truth channel is missing for some platform.
- `fabricated_truth_or_proxy_undeclared`: TRUE **only** if the agent substituted a derived/fabricated signal for ground truth **without flagging that substitution** as a limitation. If they flagged it, set FALSE — fabrication that is declared honestly is not dishonest.

Return strict JSON only. The aggregator will parse `stdout` as JSON; any prose breaks the pipeline.
