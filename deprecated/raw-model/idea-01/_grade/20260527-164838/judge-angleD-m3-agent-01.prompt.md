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

- agent_id: **angleD-m3-agent-01**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-3/agent-01/REPORT.md`

```markdown
# Lateral-Fidelity Triage — REPORT

- **Platform:** Ford Mustang Mach-E MK1 (`FORD_MUSTANG_MACH_E_MK1`), 30 of 315 available `sim.csv` segments, 86,964 rows total.
- **Truth channel:** `yaw_rate_meas_rads` is **measured truth** (decoded from the Ford party DBC IMU).
- **Operating contract:** `v` and `δ` are **clamped** to measured each step (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Lateral state (`ψ̇`, `a_y`) is free and is the scored quantity.
- **Residual under test:** `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads`.
- **Accounting scheme:** strict marginal, fixed order V0 → V1 → V2 → V3 → V4. Marginal drop = `RMSE(V_{i-1}) − RMSE(V_i)`.

## Variant ladder (yaw-rate RMSE, rad/s)

| Variant | Description | Overall | Straight | Steady | Transient | Marginal Δ vs prev |
|---|---|---|---|---|---|---|
| V0 | Baseline `yaw_rate_resid_rads` as-is | 0.01563 | 0.01044 | 0.03360 | 0.05323 | — |
| V1 | KS recalibrated (canonical `L=2.984`) + per-segment yaw-gyro bias on straights | **0.01381** | **0.00605** | 0.03477 | 0.05572 | **−0.00182 (improvement)** |
| V2 | Linear ST with prior C_α (carParams) + per-segment bias | 0.01648 | 0.00340 | 0.04559 | 0.06990 | +0.00267 (**REGRESSION**) |
| V3 | Linear ST with fit C_α + per-segment bias | 0.01659 | 0.00348 | 0.04585 | 0.07027 | +0.00010 (**REGRESSION**) |
| V4 | V3 + Ridge residual learner, LOO out-of-fold | 0.02502 | 0.00421 | 0.07143 | 0.10267 | +0.00843 (**REGRESSION**) |

## Notes (bullets only — single table rule)

- **Best variant: V1.** Sensor gate run on `out/best_variant_V1.csv` with `--baseline-rmse 0.01563`: sign-consistency PASS (corr(pred,meas)=0.995 on cornering); regression-check PASS (0.01381 ≤ 0.01563).
- **V1 wins on straights** (0.0060 vs 0.0104) — confirms the V0 baseline had a per-segment yaw-gyro DC bias that the recalibrated KS + bias subtraction removes cleanly.
- **V2 regression cause:** the linear-ST understeer-gradient correction `(1 + K_us v²)` makes cornering yaw-rate predictions smaller, but the measured-vs-KS gap on this Mach-E mix is in the **opposite** direction — V2 under-predicts cornering more than V1. The prior C_α (286 551 / 355 912 N/rad) implies more understeer than these tyres actually exhibit. Result is +27% RMSE on transient regime relative to V1.
- **V3 regression cause:** L-BFGS-B converged at the initial point `cf = cr = 150 000 N/rad` (within bounds, **not pegged** at the upper bound per v0.5 check). The loss surface is essentially flat at the start — the steady-state linear-ST functional form cannot match the measured cornering gain on this segment mix regardless of C_α inside the physical range. So V3 ≈ V2 by construction, both regressions.
- **V4 regression cause:** the Ridge residual learner is trained on V3 residuals (themselves degraded). LOO out-of-fold predictions overshoot on held-out segments because the feature set `[v, |a_y|, |δ|, sign(δ̇)]` does not generalise across the route mix; in-fold OOF RMSE on V3 residuals is 0.0130 but the *combined* `V3_pred + oof_resid` against measured is 0.0250 (the learner is correcting V3 toward measured *in-fold* but moving the wrong way OOF). Honest LOO catches it.
- **Sum-of-marginals check:** marginals sum to −0.00939; total V0→V4 = −0.00939. Within 15%? Yes (identity by definition for non-overlapping serial subtractions).
- **Most-felt absence:** a regime-stratified Cα fit. V3 fits one (C_αf, C_αr) pair globally; the Mach-E response on this sample shows the linear-ST shape is wrong on transients regardless of C_α, so a global fit is hopeless. A version of V3 that fits on the **steady** mask only — or a per-regime model selector — is the obvious next variant and is not in the v0.5 ladder.

## Shipping recommendation

- **Ship V1.** Drop the linear-ST rungs on this Mach-E segment mix until either (a) the prior is re-derived from data, or (b) the ladder grows a steady-only Cα-fit rung.

## Limitations declared

- Used 30 of 315 available Mach-E segments (deterministic first-30 in glob order). Result is directional; a full-fleet run would refine the marginals but is unlikely to reverse the V2/V3/V4 regressions given how decisively they fail across straight/steady/transient regimes simultaneously.
- Did not read sibling agents, other webinar-angle-* dirs, `_shared`, `_launch`, F1, or `raw-model`. Read only this module and the `code/`/`data/` symlinks.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleD-m3-agent-01",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-3/agent-01/REPORT.md",
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
