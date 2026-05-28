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

- agent_id: **angleE-m2-agent-01**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-2/agent-01/REPORT.md`

```markdown
# REPORT — lateral-fidelity workflow (workshop scaffold S2)

## Platform and contract

- Platform scored: **FORD_MUSTANG_MACH_E_MK1** (Ford Mustang Mach-E MK1, 315 segments, 913 626 rows).
- `yaw_rate_meas_rads` is measured truth (rlog IMU, Ford-only). Residual under test: `yaw_rate_resid_rads = yaw_rate_pred − yaw_rate_meas`.
- Speed `v` and steering `δ` are **clamped to measured** under the speed-known operating contract (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). The lateral residual is the *only* metric. No "fix" via unclamping.
- Regime split (fixed thresholds): straight 785 093 rows, steady 106 978, transient 21 555.

## Variant ladder

| variant | overall | straight | steady | transient |
|---|---:|---:|---:|---:|
| V0 (baseline KS as-shipped) | 0.01613 | 0.00877 | 0.03173 | 0.05680 |
| V1 (KS recalib L + per-segment straight-row yaw-gyro bias) | **0.01469** | **0.00493** | 0.03168 | 0.05730 |
| V2 (Linear ST, openpilot prior Cα) | 0.01653 | 0.00701 | 0.03450 | 0.06234 |
| V3 (Linear ST, fit Cα, L-BFGS-B in (5e4, 5e5) N/rad) | 0.01663 | 0.00700 | 0.03482 | 0.06266 |

V3 fit returned C_α_f = C_α_r = 1.50e5 (= x0); not pegged at the upper bound, but L-BFGS-B did not move off the initialisation. Treated as a soft regression flag (see below).

## Attribution

Marginal drop in overall RMSE (negative = improvement, positive = regression):

- **V0 → V1: −0.00144 rad/s (−8.9 %).** Real improvement; concentrated almost entirely in the straight regime (−0.00384 rad/s, −43.8 %). Steady and transient essentially unchanged. Physical reading: this is a per-segment yaw-gyro DC offset, not a vehicle-dynamics correction.
- **V1 → V2: +0.00184 rad/s (regression).** Switching from KS to Linear ST with openpilot prior cornering stiffnesses degrades every regime. The understeer term `K_us · v²` over-softens predicted yaw at the speeds this dataset spends time in, given the prior Cα.
- **V2 → V3: +0.00010 rad/s (regression).** Negligible; the L-BFGS-B fit did not move off x0 = (1.5e5, 1.5e5). With v and δ clamped and yaw dominated by straight-line rows where Cα does little work, the loss is near-flat at init.
- **Sum of marginals vs. total V0 → V3:** −0.00144 + 0.00184 + 0.00010 = +0.00050 ≈ total V0→V3 (+0.00050). Within 15 %: yes (exact, by construction).

**Net conclusion: the ladder peaks at V1.** V2 and V3 do not earn their inclusion.

## Regressions and physical reasons

- **V2, V3 regress past V0 on overall and on every regime.** Cause: the Linear ST understeer correction with openpilot-canonical Cα reduces predicted yaw rate at moderate v, but the actual residual budget in this dataset is dominated by (a) yaw-gyro DC offset in straight rows and (b) genuine transient dynamics the linear model also can't capture. V2 makes the straight-rows worse (yaw under-prediction now competes with a residual bias V1 fixes and V2 does not). Recommendation if the ladder were extensible: apply V1's bias *before* V2's understeer term.
- **V3 fit did not converge.** Not pegged at the upper bound (so not the flag the workflow defines), but stuck at x0. Workflow does not allow restart with new seeds; flagged here.
- **Transient regime is barely touched by anything.** V0 = 0.0568, V1 = 0.0573, V2 = 0.0623, V3 = 0.0627. The workflow has no rung that targets transient dynamics (would want a residual learner — out of scope here).

## Notes

- **Tool patch required.** `tools/step4_run_st_upgrade.py` indexes `P["L"]` etc., but `PARAM_BY_PLATFORM["FORD_MUSTANG_MACH_E_MK1"]` returns a frozen dataclass (`MachEST`), not a dict. Patched in place with a dict-or-attribute fallback over (L, l_f, l_r, m, C_alpha_f, C_alpha_r). Step ordering and physics unchanged. Without the patch step 4 raises `TypeError: 'MachEST' object is not subscriptable`.
- **What the workflow disallows that I wanted.** (i) A V4 residual learner targeting the transient regime; (ii) restarting V3's L-BFGS-B from multiple seeds to escape the stuck x0. Both forbidden by AGENTS.md ("ladder stops at V3", "do not deviate"). Recorded, not executed.
- **Most painful absent component:** an **eval rung**. With per-segment, per-regime, held-out scoring I could attribute V1's gain to sensor bias vs. dynamics, and could distinguish V3's "fit failed" from "fit succeeded, model is wrong". Three-number-per-variant reporting is not enough to discharge the user's request to say "how much each change contributed".

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleE-m2-agent-01",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-2/agent-01/REPORT.md",
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
