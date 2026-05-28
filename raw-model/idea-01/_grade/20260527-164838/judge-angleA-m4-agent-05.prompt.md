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

- agent_id: **angleA-m4-agent-05**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-4/agent-05/REPORT.md`

```markdown
# Module-4 / agent-05 — Lateral-fidelity triage (Ford Mustang Mach-E MK1)

## Setup

- **Platform scored:** `FORD_MUSTANG_MACH_E_MK1` (40 sim.csv segments, ~116k samples at 50 Hz, deterministic seed=42 sample from the 315 available Mach-E segments).
- **Truth channel:** `yaw_rate_meas_rads` — the IMU-**measured** yaw rate decoded from the rlog, not predicted, not clamped.
- **Predicted channel:** `yaw_rate_pred_rads` — the KS model's yaw-rate output. Residual under test: `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads`.
- **Speed-known contract:** both `v_mps` and `delta_road_rad` are **clamped** to the measured signal at every integrator step. The lateral state is what the model **predicts** under that clamped input. Speed-state RMSE is zero by construction and is not the metric.
- **Methodology consistency:** the **same segment set** and **same regime mask** are held constant across every variant row. The only thing that changes between rows is the prediction model.

## Regime mask (held constant)

- **straight:** `|delta_road_rad| < 0.01 rad`
- **steady cornering:** `|delta_road_rad| ≥ 0.01 rad` ∧ `|d(delta_road_rad)/dt| < 0.05 rad/s`
- **transient cornering:** `|delta_road_rad| ≥ 0.01 rad` ∧ `|d(delta_road_rad)/dt| ≥ 0.05 rad/s`

Sample counts: straight 100 526; steady 11 806; transient 3 630.

## Variant ladder

Accounting scheme: **strict marginal** in fixed order V0→V1→V2→V3. The ΔRMSE column is `RMSE(V_i) − RMSE(V_{i-1})` (negative = improvement, positive = regression). `|Σmarg − total|/total ≈ 0` — attribution coherent.

| Variant | Description | RMSE overall (rad/s) | Straight | Steady | Transient | ΔRMSE vs prev |
|---|---|---:|---:|---:|---:|---:|
| V0 | KS as shipped (`yaw_rate_resid_rads` from CSV, no preprocessing)                                                                                | 0.02570 | 0.01009 | 0.05629 | 0.08928 | — |
| V1 | KS recalibrated with canonical `L`; per-segment yaw-gyro bias subtracted on straights                                                            | 0.02463 | 0.00505 | 0.05672 | 0.09061 | -0.00107 |
| V2 | Linear ST with openpilot **prior** `C_α` (286.5 / 355.9 kN/rad); per-segment straight-bias subtraction reapplied                                 | 0.02531 | 0.00348 | 0.05873 | 0.09435 | +0.00068 |
| V3 | Linear ST with **fit** `C_α` (grid + L-BFGS-B, bounded 50–500 kN/rad; converged to `C_αf = C_αr ≈ 418 kN/rad`, not pegged); same bias            | 0.02505 | 0.00358 | 0.05809 | 0.09340 | -0.00025 |

**Headline:** V0→V3 total RMSE drop = **0.00064 rad/s** (2.5% reduction). Largest single improvement comes from **V1 alone** (0.00107 rad/s, 4.1%); V2 partially reverses it.

## What each variant did and contributed

- **V0 → V1 (-0.00107 rad/s, only large gain).** Two things changed: canonical `L = 2.984 m` from `PARAM_BY_PLATFORM` replaces the as-shipped value; per-segment yaw-gyro bias subtracted on straights. Almost all benefit lands in *straight* (0.0101 → 0.0051, halved) — bias is a DC fix and cannot help during cornering.
- **V1 → V2 (+0.00068 rad/s, REGRESSION).** Swapping KS for linear-ST steady-state with openpilot prior `C_α` **worsens** overall RMSE. Straight keeps dropping (0.0051 → 0.0035) because ST≈KS at small δ, but steady (0.0567 → 0.0587) and transient (0.0906 → 0.0944) cornering both worsen. **Physical cause:** the openpilot Mach-E `C_α` prior is stiffer than the actual tyres want. ST with too-stiff tyres under-predicts yaw rate during cornering (denominator `1 + K_us·v²` too small). This replicates the regression the reference catalogue predicts.
- **V2 → V3 (-0.00025 rad/s).** Fitting `(C_αf, C_αr)` by grid + L-BFGS-B refinement (the bare `triage.fit_c_alpha` returned its `x0` unchanged — gradient too shallow) found `C_αf = C_αr ≈ 418 kN/rad`, well below 500 kN/rad ceiling — **not pegged**. Recovers most of V2's damage but does not exceed V1.
- **V4 (residual-learner, LOO) — dropped as flagged regression.** Ridge on `[v, |a_y_pred|, |δ|, sign(δ̇)]` LOO against V3 residual gave overall 0.02583 — *worse* than V3. Per SKILL discipline, ship V3 and call V4 a regression rather than fold in-fold numbers and lie. Likely cause: V3 residual is dominated by transient-cornering slip dynamics that linear ST is the wrong basis to subtract, and four hand-picked features don't carry enough phase information.

## Honest conclusion

Best shipped variant is **V1**. V2 is a flagged regression caused by the openpilot ST prior being stiffer than Mach-E tyres want; V3 partially repairs V2 but does not exceed V1. The headline workshop finding — recalibrated KS beats prior-ST in cornering on this platform — replicates.

## Methodological note

`triage.fit_c_alpha` returning its initial guess *exactly* is a silent bug surface: scipy's L-BFGS-B reports success even when it never left `x0` because the local gradient is sub-tolerance. Worth a SKILL ratchet.

## Limitations

- Only 40 of 315 Mach-E segments scored (~13%) for budget.
- Per-segment bias subtraction applied in V2/V3 too, so the V2 regression is not an artefact of V1's bias step being absent later.
- F-150 Lightning not run for cross-platform corroboration.
- Did not re-run `code/ks_model.py` from scratch; used already-produced `sim.csv` predictions for V0 and recomputed yaw-rate gains for V1–V3 algebraically via `triage.ks_yaw_rate` / `triage.linear_st_yaw_rate`.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleA-m4-agent-05",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-4/agent-05/REPORT.md",
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
