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

- agent_id: **angleD-m3-agent-03**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-3/agent-03/REPORT.md`

```markdown
# REPORT.md — webinar-angle-D / module-3 / agent-03

## Headline

- **Best variant: V2** — linear single-track with prior `C_α` from `PARAM_BY_PLATFORM`.
- Overall yaw-rate residual **RMSE 0.01403 → 0.00840 rad/s** = **40.1 % drop** vs V0.
- Sensor gate (`skills/lateral-fidelity-triage/sensor.py out/best_variant_V2.csv`) **PASSED** both checks: sign-consistency `corr(pred, meas) = 0.997` on cornering, and `RMSE(V2) = 0.00840 ≤ V0 = 0.01403`.

## Setup

- Platform: **FORD_MUSTANG_MACH_E_MK1** (Ford Mach-E Mk1). `yaw_rate_meas_rads` is the **measured** truth channel from the Ford party DBC.
- Inputs `v_mps` and `delta_road_rad` are **clamped to measured** under the speed-known contract (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Lateral-only metric.
- Segment set: first 12 Mach-E segments under `data/sim/segments/FORD_MUSTANG_MACH_E_MK1/`, concatenated to **34 786 rows**.
- Regime mask thresholds: straight `|δ|<0.01 rad`; steady `|δ|≥0.01 ∧ |δ̇|<0.05`; transient `|δ|≥0.01 ∧ |δ̇|≥0.05`. Held constant across all rows.
- Attribution: **strict marginal**, fixed order V0→V1→V2→V3→V4. Marginal sum 0.004039 vs total drop V0→V4 0.004039 (0 % gap, well inside the 15 % rule).

## Variant ladder

| Variant | Overall RMSE | Straight | Steady | Transient | Marginal Δ | Verdict |
|---|---|---|---|---|---|---|
| V0  baseline (`yaw_rate_resid_rads` as-is) | 0.01403 | 0.01261 | 0.03192 | 0.03796 | —        | reference |
| V1  KS recalibrated (canonical `L`, per-seg yaw-gyro bias on straights) | 0.00973 | 0.00737 | 0.02924 | 0.04055 | **+0.00429** | win |
| V2  linear ST, prior `C_αf=C_αr=1.5e5 N/rad`, `v_min=2` fallback | **0.00840** | **0.00390** | 0.03444 | 0.04543 | **+0.00134** | win — **best** |
| V3  linear ST, fit `C_α` (`C_αf=150 000`, `C_αr=150 000`, **not pegged**) | 0.00856 | 0.00410 | 0.03498 | 0.04568 | −0.00016 | regression: fitter sat at the L-BFGS-B seed (`1.5e5`); cornering set too thin to move the gain |
| V4  Ridge residual learner on `[v,|a_y|,|δ|,sign(δ̇)]`, LOO-CV | 0.00999 | 0.00421 | 0.04056 | 0.05696 | −0.00143 | regression: OOF worse than V3, especially on transient — features under-power the cornering structure |

## Honest regression notes

- **V3 regressed (−0.00016 rad/s)** vs V2. The fit landed on `C_αf = C_αr = 1.5e5` — identical to the optimiser seed and to the prior — but the pegged-at-upper-bound flag did **not** trigger (upper bound is `5e5`). Cause: the loss surface is flat around the prior on this segment mix (straights dominate row count), so L-BFGS-B doesn't escape the seed; the tiny degradation is noise from changes far from straights.
- **V4 regressed (−0.00143 rad/s)** vs V3 out-of-fold. Per skill v0.5 rule, V3 is what I would ship over V4 — but V2 dominates both, so V2 is shipped. Cause: the feature set `[v,|a_y|,|δ|,sign(δ̇)]` plus Ridge α=1 cannot capture transient-cornering structure when trained leave-one-segment-out; transient RMSE *rises* from 0.0457 to 0.0570.
- Per-regime, V2 nearly halves **straight** residual (0.01261 → 0.00390 rad/s — the yaw-gyro-bias subtraction doing its job). **Steady** and **transient** regimes get *worse* under V2 (0.0319 → 0.0344, 0.0380 → 0.0454) — the linear-ST gain over-rotates relative to the measured truth on this segment mix, but the straight-channel improvement dominates by row count.

## What the v0.5 skill rules prevented

- **V0-as-is rule (v0.3):** stopped me from folding the gyro-bias subtraction into V0, which would have erased V1's headline win.
- **Pegged-`C_α` rule (v0.5):** would have caught a "quiet upper-bound win"; in fact it confirmed the V3 result is *not* a peg — the L-BFGS-B sit-at-seed is a separate pathology I now flag explicitly above.
- **LOO-only rule on V4 (v0.5):** prevented an in-fold V4 "win" being reported; out-of-fold V4 is honestly worse than V3.
- **Single-table rule (v0.5):** kept the report scannable for downstream parsers.
- **ST low-`v` warning (v0.4):** `linear_st_yaw_rate` falls back to KS below 2 m/s. Mach-E segments do include sub-2-m/s rows; without the fallback the eigenvalues blow up.

## Most painful missing component and cost

- **Nonlinear / transient single-track (V2.5)**. The cost is visible in the per-regime breakdown — V2 nearly halves straight RMSE but **worsens steady and transient** (0.032 → 0.034, 0.038 → 0.045). A transient ST with proper slip-angle dynamics (or even a relaxed `|δ̇|` low-pass on the gain) would target exactly that 0.04–0.05 rad/s headroom, which is now the dominant remaining error.

## Most surprising thing

The `C_α` fitter (V3) **did not move** off its seed. With 12 Mach-E segments at 34 786 rows, the straight-line fraction dominates so heavily that the steady-cornering loss term has almost no leverage on the optimiser — meaning my "fit" is doing zero work, yet it's *also* not triggering the pegged-at-upper-bound guard because it's pegged at the **seed**, not the **bound**. The v0.5 guard is necessary but not sufficient; a "stuck at x0" guard would be the natural v0.6 addition.

## Sensor

- Ran: `python3 skills/lateral-fidelity-triage/sensor.py out/best_variant_V2.csv`
- Result: PASS / PASS. It did **gate** V2 — had the sign convention been off (the v_min fallback could in principle flip behaviour at low speed), or had V2 silently come out worse than V0, the gate would have blocked the ship.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleD-m3-agent-03",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-3/agent-03/REPORT.md",
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
