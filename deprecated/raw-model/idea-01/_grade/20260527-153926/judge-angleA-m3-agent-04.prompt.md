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

- agent_id: **angleA-m3-agent-04**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-3/agent-04/REPORT.md`

```markdown
# Module-3 / agent-04 — Lateral-fidelity triage (Mach-E)

## Setup

- **Platform scored**: `FORD_MUSTANG_MACH_E_MK1`. The `yaw_rate_meas_rads` column is the **measured** truth channel from the rlog gyro — not a prediction, not a clamped state, not self-consistency.
- **Speed-known contract**: `v_mps` and `delta_road_rad` are **clamped** at every integrator step. The integrator's own speed/steer updates are discarded. The only **predicted** channels are `yaw_rate_pred_rads` and `a_y_pred_mps2`. Lateral fidelity lives entirely in the residual `pred − meas`.
- **Segments used**: 60 Mach-E `sim.csv` files (first 60 lexicographic), 173 940 rows at 50 Hz. Same segment set, same regime mask, every row.
- **Regime mask**: straight `|δ_road|<0.01`; steady `|δ|≥0.01 ∧ |dδ/dt|<0.05`; transient `|δ|≥0.01 ∧ |dδ/dt|≥0.05`.
- **Parameters**: `PARAM_BY_PLATFORM["FORD_MUSTANG_MACH_E_MK1"]`. `L=2.984 m`, `m=2336 kg`, `I_z=4879.05`, `l_f=1.313`, `l_r=1.671`, `C_αf_prior=286 551`, `C_αr_prior=355 912 N/rad`, `i_s=17`.
- **Sign check**: `corr(δ_road, ψ̇_meas) = +0.93` on cornering — left-positive convention OK.
- **Attribution scheme**: strict marginal in fixed order V0→V1→V2→V3→V4. Marginals sum to total within float epsilon.

## Variant ladder — RMSE on `yaw_rate_resid_rads`, rad/s

| Variant | Overall | Straight | Steady cornering | Transient cornering | Marginal Δ overall |
|---|---:|---:|---:|---:|---:|
| V0 baseline (column as-is)                       | 0.012144 | 0.008508 | 0.025192 | 0.048887 | — |
| V1 KS recal + per-seg yaw-gyro bias              | 0.010552 | 0.005064 | 0.026019 | 0.051156 | **-0.001593** (improves) |
| V2 Linear ST with prior C_α + bias               | 0.012480 | 0.003346 | 0.034243 | 0.063623 | **+0.001929** (regression) |
| V3 Linear ST with fit C_α + bias                 | 0.012597 | 0.003430 | 0.034580 | 0.063980 | **+0.000116** (regression) |
| V4 Ridge residual learner on V3 (LOO CV)         | 0.010045 | 0.003510 | 0.025443 | 0.053823 | **-0.002551** (improves) |

Total drop V0→V4 = **0.002099 rad/s (17.3% relative)**. Sum of marginals = 0.002099 (exact).

## What each variant did

- **V1** — Recompute `ψ̇ = (v/L)·tan(δ_road)` with canonical L, subtract per-segment yaw-gyro bias from straights (≥10 samples). Mean bias ≈ 1.82e-4 rad/s; median 7.12e-4. Largest physically-motivated win: straight-line RMSE drops 40% (0.0085 → 0.0051).
- **V2** — Linear single-track steady-state gain `ψ̇_ST = vδ/(L(1+K_us v²))` with openpilot prior `C_α` + same bias. Improves straight (bias absorbs cleanly) but **worsens cornering substantially**: steady +36%, transient +24%. This is the regression `references/ks-vs-st.md` warns about — the openpilot prior `C_α` is *stiffer than the Mach-E tyres actually behave*, so the linearisation over-damps yaw and predicted `ψ̇` falls below measured.
- **V3** — Fit `(C_αf, C_αr)` on segment set via L-BFGS-B, bounds (5e4, 5e5) N/rad. Optimiser returned `(1.5e5, 1.5e5)` — exactly the initial guess — indicating a flat / non-smooth local loss; coarse grid confirms ~1.4% variation across the bounded box (best ≈ 0.01320 at 3e5, 3e5 vs 0.01339 at the prior). **Fit doesn't beat V2 in real terms** — flagged as regression.
- **V4** — Ridge on `[v, |a_y|, |δ|, sign(δ̇)]` against V3 residuals with **leave-one-segment-out** CV. Recovers everything V2+V3 lost and pushes overall below V1 (0.01005 < 0.01055).

## Regressions, named honestly

- **V2 regression** vs V1 on every cornering regime. Openpilot's Mach-E prior `C_α` is too stiff for these tyres on these roads, so ST over-damps yaw rate. KS over-predicts; ST with this prior over-corrects.
- **V3 also a regression** vs V1. Implied lesson: this is the wrong DoF to vary.
- **V4 positive overall** but it is *learning the residual*, not adding physics. Whatever it captures is an admission that the dynamics rung above is incomplete.

## Limitations

- Only 60 of 315 available Mach-E segments used in budget.
- No F-150 Lightning run for comparison.

## Component I most felt the lack of

A **calibrated steering-ratio / EPS-compliance correction module** between V1 and V2. The big residual on cornering is not "wrong Cα" but "δ_road derived from `delta_wheel_deg / i_s` understates the actual road-wheel angle under torque load on this rack". Without a rack-compliance term I had to leave that gap unaddressed and let V4 launder it as a learned residual — exactly the dishonest credit-allocation the skill is designed to prevent.

Files: `out/run_ladder.py`, `out/ladder_results.json`.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleA-m3-agent-04",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-3/agent-04/REPORT.md",
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
