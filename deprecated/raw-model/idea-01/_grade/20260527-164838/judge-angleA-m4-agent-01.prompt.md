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

- agent_id: **angleA-m4-agent-01**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-4/agent-01/REPORT.md`

```markdown
# Module-4 / agent-01 — Lateral-fidelity variant ladder (Mach-E)

## Setup

- **Platform.** `FORD_MUSTANG_MACH_E_MK1` (40 of 315 sim.csv segments, 115 970 rows at 50 Hz). Mach-E chosen because its `sim.csv` carries decoded IMU `yaw_rate_meas_rads` truth; Tesla does not.
- **Scored channel.** `yaw_rate_meas_rads` is the **measured** truth (IMU yaw gyro decoded from rlog). All variants score `pred − measured` RMSE against this same column.
- **Contract.** Operating under the speed-known / lateral-only contract: `v_mps` and `delta_road_rad` are **clamped** to measurement at every integration step. The integrator's `v`/`δ` updates are overwritten. The **predicted** channels are `yaw_rate_pred_rads` (V0) and recomputed yaw-rate from each variant (V1..V4). Speed-state agreement is zero by construction and not scored. No variant unclamps `v` or `δ`.
- **Methodology consistency.** Segment set (same 40 sim.csv files) and regime mask **held constant across every row**. Bias-correction in V1..V3 computed only on each segment's straight-line samples and applied uniformly.
- **Regime mask** (from `triage.regime_mask`):
  - `straight` — `|δ_road| < 0.01 rad` (103 083 rows)
  - `steady cornering` — `|δ_road| ≥ 0.01` ∧ `|dδ/dt| < 0.05 rad/s` (10 610 rows)
  - `transient cornering` — `|δ_road| ≥ 0.01` ∧ `|dδ/dt| ≥ 0.05 rad/s` (2 277 rows)
- **Attribution accounting.** Strict marginal, fixed order V0→V1→V2→V3→V4. By construction marginals sum to total drop (attribution coherence ≈ 0%, well inside the 15% budget).

## Variant ladder

| Variant | Description | RMSE overall (rad/s) | Straight | Steady | Transient | Δ marginal (rad/s) |
|---|---|---:|---:|---:|---:|---:|
| V0 | Baseline `yaw_rate_resid_rads` as-stored, no preprocessing                                                                                  | 0.01394 | 0.00929 | 0.02726 | 0.05028 | — |
| V1 | KS recalibrated: `ψ̇ = (v/L)·tan(δ)` with canonical `L=2.984` from `PARAM_BY_PLATFORM`; minus per-segment yaw-gyro bias on straight samples | 0.01242 | 0.00551 | 0.02822 | 0.05265 | -0.00152 |
| V2 | Linear ST with **prior** `C_αf=286 551, C_αr=355 912 N/rad`; KS fallback below v=2 m/s; per-segment straight bias subtracted                | 0.01490 | 0.00345 | 0.03728 | 0.06553 | +0.00248 |
| V3 | Linear ST with **fit** `C_αf=350 000, C_αr=350 000 N/rad` (grid search 50k–500k; L-BFGS-B fell back to x0 — loss surface non-smooth near `K_us·v²≈-1`) + bias | 0.01455 | 0.00367 | 0.03610 | 0.06398 | -0.00036 |
| V4 | Ridge regression on V3 residuals with features `[v, |a_y|, |δ|, sign(δ̇)]`, **leave-one-segment-out** CV                                    | 0.01120 | 0.00380 | 0.02484 | 0.05350 | -0.00334 |

**Headline:** RMSE 0.01394 → 0.01120 rad/s, **−19.6%** total. Attribution `|Σmarg − total|/total ≈ 0` (consecutive-difference accounting).

## Findings and physical reasoning

- **V1 carries most of the legitimate-physics gain.** Per-segment straight-line yaw-gyro bias cuts the straight-regime residual nearly in half (0.00929 → 0.00551). Gain in cornering is essentially zero — KS still has no slip.
- **V2 is a regression.** Δ = **+0.00248 rad/s worse**, especially steady and transient cornering. Openpilot ST prior `C_αf=286k, C_αr=355k` is **stiffer than the Mach-E tyres actually want** under measured inputs — ST over-predicts yaw rate in cornering. Matches `references/ks-vs-st.md`'s "ST prior too stiff for Mach-E tyres" warning.
- **V3 is a partial recovery, still regression vs V1.** Fitting `C_α` over the Mach-E set drives Cf/Cr toward the upper range (≈350k after a 19×19 grid + Nelder-Mead). Still worse than V1 because linear-ST functional form is wrong class for the non-linear slip behaviour in the data. Fit did not peg at upper bound (overfit flag), but landed on a flat plateau.
- **V4 is the real win.** A small ridge on 4 features reclaims the cornering structural error and beats both V1 and V0. Critically out-of-fold (leave-one-segment-out): every prediction comes from a model that has never seen its own segment. Lifts cornering regimes (steady 0.0361 → 0.0248; transient 0.0640 → 0.0535) — exactly where KS/ST's missing slip-angle dynamics dominate. Straight RMSE essentially unchanged.

## Honest regression flags

- **V2 worsened V1 by +1.93 mrad/s.** Cause: stiffer-than-real prior `C_α` over-predicts yaw in cornering.
- **V3 worsened V1 by +1.62 mrad/s** (even after `C_α` fit). Cause: linear-ST functional form cannot represent the non-linear slip; fitting in a wrong model class moves you along a wrong manifold.
- V4 is the only rung that beats V1.

## Methodological finding

The supplied `triage.fit_c_alpha` silently fails: L-BFGS-B returns its starting point `(1.5e5, 1.5e5)` because the loss surface is non-smooth around `K_us·v² = −1`, and `pegged` only checks the upper bound. A 19×19 grid search exposed the true plateau at ≈350 kN/rad. Reference text warns about pegging at the upper bound but says nothing about this near-`K_us·v² = −1` cliff. A naïve run would have shipped V3=V2.

## Limitations

- 40-of-315 segment sample chosen by sort order for reproducibility in budget.
- V4 model intentionally tiny (4 features, ridge α=1.0). A larger class could push further; the workshop bound is small ML + LOSO.

Files: `out/run_ladder.py`, `out/ladder.json`.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleA-m4-agent-01",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-4/agent-01/REPORT.md",
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
