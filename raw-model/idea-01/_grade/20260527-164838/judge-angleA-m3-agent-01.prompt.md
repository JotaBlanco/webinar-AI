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

- agent_id: **angleA-m3-agent-01**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-3/agent-01/REPORT.md`

```markdown
# Module-3 / agent-01 — Lateral-fidelity variant ladder (Mach-E)

## Setup

- **Platform scored**: `FORD_MUSTANG_MACH_E_MK1`. `yaw_rate_meas_rads` is **measured** truth decoded from the rlog IMU — not a prediction, not the integrator's own state.
- **Segments used**: first 80 Mach-E segments (deterministically sorted), 231 926 rows.
- **Speed-known contract**: `v_mps` and `delta_road_rad` **clamped** to measurement at every step; the **predicted** channel is `yaw_rate_pred_rads`. Residual under test: `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads`. Speed/steering state agreement is zero by construction and is not the metric.
- **Sign check**: `corr(δ_road, ψ̇_meas) = +0.909` on cornering samples — left-positive convention confirmed.
- **Regime mask** (constant): straight `|δ|<0.01`; steady `|δ|≥0.01 ∧ |δ̇|<0.05`; transient `|δ|≥0.01 ∧ |δ̇|≥0.05`. Counts: 211 404 / 17 627 / 2 895.
- **Parameters**: `PARAM_BY_PLATFORM["FORD_MUSTANG_MACH_E_MK1"]` — `L=2.984`, `l_f=1.313`, `l_r=1.671`, `m=2336`, `I_z=4879.05`, `C_αf=286 551`, `C_αr=355 912 N/rad`.
- **Attribution scheme**: strict marginal in fixed order V0→V1→V2→V3→V4. Marginal drop = `RMSE(V_{i-1}) − RMSE(V_i)`. Sum of marginals within 0% of total drop (well under 15% bar).

## Variant ladder — RMSE on `yaw_rate_resid_rads` (rad/s)

| Variant | Overall | Straight | Steady | Transient | Marginal drop |
|---|---:|---:|---:|---:|---:|
| V0 baseline (KS as-is)                  | 0.01190 | 0.00853 | 0.02331 | 0.05219 | — |
| V1 KS recal + per-segment yaw bias      | 0.01013 | 0.00498 | 0.02395 | 0.05406 | -0.00176 |
| V2 Linear ST, prior C_α (regression)    | 0.01201 | 0.00433 | 0.03121 | 0.06518 | +0.00187 |
| V3 Linear ST, multistart-fit C_α        | 0.01180 | 0.00412 | 0.03072 | 0.06462 | -0.00020 |
| V4 Ridge residual learner on V3, LOSO   | 0.01003 | 0.00422 | 0.02433 | 0.05614 | -0.00178 |

Total drop V0→V4 = 0.00187 rad/s. Sum of marginals = 0.00187 rad/s. **Final overall RMSE = 0.01003, a 15.7% improvement vs V0.**

## Variants

- **V0** — `yaw_rate_resid_rads` from the CSV. Per the baseline-methodology contract.
- **V1** — recompute `ψ̇=(v/L)tan(δ)` with canonical L; subtract per-segment yaw-gyro bias from straights (≥50 samples), median bias = +0.00071 rad/s.
- **V2** — linear ST steady-state gain with **openpilot prior** C_α. Same per-segment bias as V1.
- **V3** — fit `(C_αf, C_αr)` bounded to (5e4, 5e5) N/rad. The skill's stock `fit_c_alpha` (single L-BFGS-B start at (1.5e5, 1.5e5)) traps in a flat-gradient region; multistarted from five points and kept best (Cf=Cr≈2.0e5, loss 0.01266). Neither bound pegged.
- **V4** — `sklearn.linear_model.Ridge(alpha=1)` on `[v, |a_y|, |δ|, sign(δ̇)]` against V3 residuals with **leave-one-segment-out** CV. Out-of-fold scoring only.

## Regressions and physical causes

- **V2 is a regression vs V1.** Openpilot's prior C_α (286k/356k N/rad) is stiffer than these Mach-E tyres behave, so ST under-rotates at meaningful slip, worsening cornering by ≈30–40% relative to V1. Matches the `references/ks-vs-st.md` "Known regression" warning. The skill made me **more honest, not more optimistic**.
- **V3 is a near-zero recovery, still worse than V1.** Fitted Cf=Cr≈2.0e5 — *softer* than the openpilot prior — but the steady-state ST gain is structurally the wrong shape for the slip dynamics in the data (transient/phase, not steady gain).
- **V2/V3's straight RMSE is *lower* than V1's** (0.0043/0.0041 vs 0.0050) — numerical wash from how bias cleanup interacts with the small-δ limit.
- **V4 recovers what V2/V3 lost** and edges past V1 by 0.00010 rad/s. A small residual learner on KS+bias alone would have got most of V4's win without the ST detour.

## Notes / limitations

- No `evals/` harness in this module to validate report format — self-audited.
- Used first 80 of 315 Mach-E segments for runtime; the V2 regression is the headline regardless of scale.
- The skill's `fit_c_alpha` single-start L-BFGS-B is fragile on this loss surface; patched in `tools/run_ladder.py` with a multistart, but did not modify the skill (read-only).

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleA-m3-agent-01",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-3/agent-01/REPORT.md",
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
