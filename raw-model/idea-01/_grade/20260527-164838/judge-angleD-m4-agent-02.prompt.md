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

- agent_id: **angleD-m4-agent-02**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-4/agent-02/REPORT.md`

```markdown
# REPORT — webinar-angle-D / module-4 / agent-02

## Headline

Lateral yaw-rate RMSE on 12 Ford Mustang Mach-E segments dropped from
V0 = 0.01403 rad/s to V2 = 0.00825 rad/s — a 41 % reduction. V2 (Linear
single-track with prior Cα + yaw-gyro bias) is the shipped best
variant. V3 and V4 are honest regressions and are not shipped.

- Platform: FORD_MUSTANG_MACH_E_MK1.
- `yaw_rate_meas_rads` is **measured** truth (Ford party-DBC yaw gyro).
- `v` and `δ` are **clamped to measured** under the speed-known contract; speed/steering-state agreement is scope, not metric.
- Attribution: strict marginal, fixed order V0→V1→V2→V3→V4. Sum of marginals 0.004031 = total drop 0.004031 (within 15 %, in fact identical).
- Sensor gate (`sensor.py out/best_variant.csv`): PASS sign-consistency (corr 0.997 on cornering), PASS regression-check (0.00825 ≤ 0.01403).

## Variant ladder

| variant | overall | straight | steady | transient |
|---|---:|---:|---:|---:|
| V0 baseline (as-is) | 0.01403 | 0.01261 | 0.03192 | 0.03796 |
| V1 KS recal + yaw-bias | 0.00973 | 0.00737 | 0.02924 | 0.04055 |
| V2 Linear ST (prior Cα) | **0.00825** | **0.00351** | 0.03459 | 0.04544 |
| V3 Linear ST (fit Cα) | 0.00839 | 0.00367 | 0.03517 | 0.04570 |
| V4 + residual learner (LOO) | 0.00999 | 0.00379 | 0.04116 | 0.05839 |

Units: rad/s. Bold = shipped best.

## Composition decision

- Two skills loaded: `regime-segmentation` v0.3 (tags every row straight/steady/transient) and `lateral-fidelity-triage` v0.5 (the 5-step ladder + sensor gate).
- Order: `regime-segmentation` first — it is a pure DataFrame transform, and the triage ladder calls `per_regime_rmse` on the tagged frame. Triage second — it owns the analytical playbook (V0..V4, marginal accounting, sensor).
- `tools/run_ladder.py` is the thin glue that loads, tags, runs the ladder, writes `out/best_variant.csv` and `out/summary.json`.

## What each change contributed (strict marginal, V0→V4)

- V0→V1: −0.00429 rad/s overall. KS recalibration with canonical `L` from `parameters.py` plus per-segment yaw-gyro bias subtraction on straight-line samples. The bias term is what kills the straight-line residual (0.01261 → 0.00737).
- V1→V2: −0.00148 rad/s overall. Switching from kinematic to steady-state linear single-track with prior Cα removes the residual oversteer of pure KS — straight-line drops further (0.00737 → 0.00351), the structural gain term `1/(1 + K_us v²)` is doing real work at highway speed.
- V2→V3: **+0.00014 rad/s — regression.** Fitted Cα = (150000, 150000) N/rad. These are exactly the L-BFGS-B initial guesses (`x0 = [1.5e5, 1.5e5]`); the optimizer made no measurable progress and just paid the optimisation noise. Not pegged, but effectively a no-op-with-noise. V2 wins outright.
- V3→V4: **+0.00160 rad/s — regression.** Out-of-fold Ridge on `[v, |a_y|, |δ|, sign(δ̇)]` does not generalise across these 12 segments; LOO oof_rmse 0.00999 > V3's 0.00839. Per the v0.5 rule: ship V3 (here V2), not V4.

Total drop V0→V2 (shipped): 0.00578 rad/s = 41 %.

## Painful absence

The skill pair lacks an **eval/golden-residual fixture**. Without a known-good per-regime RMSE checked in, the only way to notice if `parameters.py` or the CSVs changed under our feet is the sensor's coarse "no worse than V0" check, which still passes for a 5 % regression. A second sensor that locks in the *expected* RMSE for V1 and V2 (within a tolerance) would have surfaced the v3 fit collapse instantly.

A second painful absence: the ladder skill has no notion of **highway-only vs urban** sub-regimes within "transient cornering". Transient RMSE rises across every variant (0.038 → 0.058), so every "win" is happening on straight + steady at the cost of transient. The mask treats the worst regime as a single bucket.

## What rules prevented

- The v0.3 V0-methodology rule prevented folding the yaw-gyro bias into V0 — keeping it inside V1 is what makes the V0→V1 marginal honest (−0.00429 rad/s rather than ~0).
- The v0.5 regression-flagging rule forced V3 and V4 to be named as regressions rather than buried under a "+/−" wash.
- The v0.5 single-table rule kept this report parseable downstream — exactly one markdown table, the ladder.
- The v0.5 pegged-Cα detection ran (returned False) but pointed at the deeper issue: fit *didn't peg*, but it also didn't move — a finding the rule indirectly surfaced.
- The v0.4 low-v `v_min ≈ 2 m/s` fallback inside `linear_st_yaw_rate` is what kept V2/V3 from blowing up on any Lightning-style stationary stretches that exist in the Mach-E set.
- The v0.5 sensor gate confirmed sign-consistency (corr 0.997) before declaring V2 the best variant.

## Surprise

V2 outperforms V3 even though V3 is allowed to fit Cα freely. The reason is mechanical: L-BFGS-B starts at `x0 = [1.5e5, 1.5e5]` and the loss surface near that point is shallow/noisy enough that the optimizer terminates without progress. The "fit" is identical to the prior — except it inherits a tiny bit of numerical jitter and *loses* by 0.00014 rad/s overall. Free parameters can still lose to fixed parameters when the optimiser is the bottleneck, not the model.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleD-m4-agent-02",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-4/agent-02/REPORT.md",
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
