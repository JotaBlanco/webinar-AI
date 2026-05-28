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

- agent_id: **angleA-m3-agent-05**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-3/agent-05/REPORT.md`

```markdown
# Module-3 / agent-05 — Lateral-fidelity triage (Mach-E)

## Setup

- Platform scored: **FORD_MUSTANG_MACH_E_MK1**. `yaw_rate_meas_rads` is the **measured** yaw-rate channel from the rlog IMU (not predicted, not self-consistency).
- Speed-known contract: `v_mps` and `delta_road_rad` are **clamped** to measured signals. The integrator's `v`/`δ` updates are overwritten every step. Only quantity under test is `yaw_rate_pred_rads`; residual = `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads`.
- Segment set: first 80 of 315 Mach-E `sim.csv` files (231 926 rows — 211k straight / 17.6k steady / 2.9k transient). Identical segment-set and identical regime mask for every row.
- Regime mask (`triage.regime_mask`): straight `|δ|<0.01`; steady `|δ|≥0.01 ∧ |dδ/dt|<0.05`; transient `|δ|≥0.01 ∧ |dδ/dt|≥0.05`.
- Parameters: openpilot-canonical from `PARAM_BY_PLATFORM` (L=2.984, l_f=1.313, l_r=1.671, m=2336, I_z=4879.05, Cαf_prior=286 551, Cαr_prior=355 912).

## Attribution scheme

- **Strict marginal**, fixed order V0→V1→V2→V3→V4. Total drop V0→V4 = **0.00227 rad/s**. Sum of marginals = **0.00228 rad/s** (closes to within 0.5%, well under 15%).

## Variant ladder (RMSE of yaw-rate residual, rad/s)

| Variant | Overall | Straight | Steady cornering | Transient cornering | Marginal Δ overall | Notes |
|---|---|---|---|---|---|---|
| V0 baseline (resid as-is)                | 0.01190 | 0.00853 | 0.02331 | 0.05219 | — | No preprocessing |
| V1 KS recal + per-seg yaw bias           | 0.01013 | 0.00498 | 0.02395 | 0.05406 | **-0.00177** | Bias from straight-line mean residual |
| V2 Linear ST, prior Cα                   | 0.01174 | 0.00365 | 0.03104 | 0.06482 | **+0.00161** (regression) | Straight improves but cornering RMSE rises ~30% |
| V3 Linear ST, fit Cα (Nelder-Mead)       | 0.01142 | 0.00361 | 0.02995 | 0.06352 | **-0.00033** | Cαf=312 267, Cαr=318 880 — not pegged |
| V4 Residual learner on V3 (LOO)          | 0.00963 | 0.00370 | 0.02355 | 0.05525 | **-0.00179** | Ridge on [v,|a_y|,|δ|,sign(δ̇)], LOSO |

**Headline:** total drop = 19% relative (0.00227 rad/s absolute); V0 0.01190 → V4 0.00963.

## Per-variant commentary

- **V1 — KS recalibrated.** Canonical L=2.984 m and subtract per-segment straight-line yaw-gyro bias. Straight-regime RMSE halves (0.0085 → 0.0050). Cornering regimes nudge up because V0 included offsetting biases that V1 removes.
- **V2 — Linear ST with prior Cα.** *Regression.* Openpilot-canonical Cα prior is too stiff for these tyres: steady-state gain `v·δ/(L·(1+K_us·v²))` under-predicts yaw rate at moderate-to-high `|a_y|`, blowing up steady and transient regimes by ~30%. Straight regime improves only marginally (dominant straight-line term is bias, not slip).
- **V3 — Linear ST with fit Cα.** Methodology note: skill helper `triage.fit_c_alpha` uses L-BFGS-B with default finite-difference step, which produces a numerically-zero gradient at the ~1e5 parameter scale and never moves off `x0`. Re-fit with Nelder-Mead (no gradient) in `out/run_ladder.py`, bounded to (5e4, 5e5). Optimum: Cαf=312 267, Cαr=318 880 N/rad — neither bound pegged, but only 0.00033 rad/s marginal gain. Confirms ST steady-state form is structurally limited for transient cornering (no tyre relaxation lag, no slip-angle dynamics).
- **V4 — Residual learner.** Small Ridge regressor (α=1) on `[v, |a_y|, |δ|, sign(δ̇)]` against V3 residuals, leave-one-segment-out. OOF RMSE improves to 0.00963 — best overall and the only variant that improves transient cornering relative to V3 (0.0635 → 0.0552). The model is learning unmodelled slip and steering-rate-dependent lag.

## Regressions explicitly flagged

- **V2 (Linear ST prior)** — overall regression (-0.00161 rad/s). Physical cause: openpilot prior tyre stiffness for the Mach-E is too high for the actual rubber/load combination, so the steady-state gain predicts a smaller yaw rate than measured, biasing all cornering samples positive in residual.

## Recommendation

Ship **V1 + V4** as the production stack:
1. KS with canonical L and per-segment yaw-bias correction (V1).
2. Linear ST with fit Cα (V3) as the cornering substrate.
3. LOO-validated residual learner (V4) on top, fed `[v, |a_y|, |δ|, sign(δ̇)]`.

The ST stage carries its weight only because the residual learner can clean up after it; without V4, V1 alone would beat V2/V3 on overall RMSE.

## Methodological finding

The skill's helper `triage.fit_c_alpha` is broken in a *silent* way on this dataset: L-BFGS-B with default `eps≈1.5e-8` produces zero finite-difference gradient when parameters are O(1e5), so it returns `x0` unchanged and reports `pegged=False`. The "if it pegs at the upper bound, flag it" guard would never fire — but the fit is still degenerate. A procedure's failure mode can be invisible to the procedure's own self-check.

Files: `out/run_ladder.py`, `out/ladder_results.json`.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleA-m3-agent-05",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-3/agent-05/REPORT.md",
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
