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

evaluation:
  spec: idea-01-lateral-attribution.canonical.yaml
  primary-kpis: [yaw_rate_rmse, cte_rmse]
  pool: held-out validation set (route-stratified, never seen by agents)

deliverable:
  directory: final-model/
  required:
    - predict.py
    - manifest.json
    - REPORT.md
  optional:
    - coeffs.json
    - any other artefacts the agent's predict() depends on
  predict-signature: |
    def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
        """Returns a DataFrame aligned with sim_df.index, with columns:
        - yaw_rate_pred_rads  (required, rad/s)
        - x_m, y_m            (optional, m) — if omitted, the grader integrates
                              them from the predicted yaw_rate using the
                              measured velocity.
        platform is one of FORD_MUSTANG_MACH_E_MK1, FORD_F_150_LIGHTNING_MK1.
        """
  failed-shape-policy: |
    If predict.py fails to import, raises, or returns an unusable shape, the
    cohort report marks the submission status="failed". No partial credit.

success-metrics:
  # Outcome KPIs — graded programmatically against the held-out val pool.
  # See evaluation.spec (canonical.yaml) for definitions.
  - id: yaw_rate_rmse-improvement-pct
    type: numeric
    rubric: improvement_pct on KPI 1 (yaw-rate RMSE) vs V0 baseline
    evidence: programmatic — grading skill computes this from predict.py
  - id: cte_rmse-improvement-pct
    type: numeric
    rubric: improvement_pct on KPI 2 (distance-resampled CTE RMSE) vs V0 baseline
    evidence: programmatic — grading skill computes this from predict.py
  # Hygiene rubric — assessed from REPORT.md.
  - id: regime-breakdown-present
    type: binary
    rubric: the report breaks out error by regime (straight / cornering / transient), not only an aggregate
    evidence-in-report: a per-regime table or chart of either KPI
  - id: methodology-consistent
    type: binary
    rubric: same segment list and same metric definition across every variant on the ladder
    evidence-in-report: variant table shares a fixed segment-set / regime-mask declaration in its header or caption
  - id: attribution-coherent
    type: numeric
    rubric: "|Σ marginal KPI drops − total drop| / total drop (no double-counting)"
    threshold: "< 0.15"
    evidence-in-report: marginal-improvement column and total-drop value both present and reconcilable
  - id: honest-regression-flagged
    type: binary
    rubric: any variant that worsened either KPI is reported as a regression with a physical reason; vacuous if no regression occurred
    evidence-in-report: variant table includes regression rows with a physical-cause column, OR an explicit "no regressions observed" statement
```

For each item in `success-metrics`, decide PASS/FAIL/NULL and quote your evidence. For `type: numeric` items, also estimate the value the report implies and check it against the `threshold` (the rubric specifies what direction is good).

## The report — score this one only

- agent_id: **m2-agent-05**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-05/final-model/REPORT.md`

```markdown
# agent-05 — Lateral fidelity REPORT

## TL;DR

Shipped a **linear single-track steady-state** model that replaces the V0 kinematic-bicycle expression with the classical understeer-corrected form:

    yaw_rate = v * delta_road / (L + K_us * v^2)

where `K_us = (m / L) * (l_r / C_alpha_f - l_f / C_alpha_r)` is computed once at import-time from the openpilot-canonical ST parameters of each platform. No data was used to fit any coefficient — the model is purely a physics upgrade.

## Why this should beat V0

V0 (`psi_dot = (v/L) * tan(delta)`) is the bottom rung of the CommonRoad fidelity ladder. It assumes the car goes exactly where the front wheel points — no tire slip — so it **over-predicts yaw rate as speed rises**, because real cars develop lateral tire-slip that reduces the actual turning rate for a given steering angle.

The steady-state linear single-track expression is the exact closed-form solution of the dynamic bicycle model in the limit `d/dt = 0`. It encodes tire compliance through `K_us`, and at the speeds covered by the Ford rlogs (15–30 m/s typical highway / arterial) the correction factor `1 / (1 + K_us * v^2 / L)` ranges from roughly 0.9 at 15 m/s to ~0.75 at 30 m/s for these platforms. That is exactly the speed-dependent attenuation V0 is missing.

### Numeric K_us values (s² / m)

| Platform                 | L (m) | K_us (×10⁻³) |
|--------------------------|-------|--------------|
| FORD_MUSTANG_MACH_E_MK1  | 2.984 | 1.678        |
| FORD_F_150_LIGHTNING_MK1 | 3.70  | 1.677        |
| TESLA_MODEL_3            | 2.875 | 1.677        |

(The three platforms land within a percent of each other — the heavier-but-larger-wheelbase platforms balance out.)

### Expected impact on the two KPIs

- **Yaw-rate RMSE**: should drop materially in the `steady` and `transient` regimes (where V0's slip-free over-prediction bites). In `straight` (|delta| < 0.01) it converges to zero like V0 does, since `yr → 0` either way.
- **CTE RMSE**: V0 leaves a systematic heading-rate bias, which integrates into a quadratic-in-distance position error during any sustained turn. Removing the bias removes the dominant trajectory error in long curves.

## What I did NOT do (and why)

I deliberately stopped at the steady-state form. The natural next two upgrades would be:

1. A first-order lag (yaw-rate dynamics) — `tau * yr_dot + yr = yr_ss`, with `tau` derivable from `I_z, C_alpha, l_f, l_r`. Catches transient under/over-shoot.
2. A per-platform residual gain fitted on a training split — turns the model into a one-parameter regression that compensates for whatever systematic offset the steady-state form still leaves.

I could not implement (2) safely because `python3` execution was denied in this sandbox, so I could neither fit nor verify any data-derived coefficient. (1) was within reach but introduces a non-trivial integration step and risks failure on edge cases I cannot test. The shipped model is the largest improvement I can ship with **zero risk of regression on the V0 baseline at any speed**: at v→0 it reduces to V0 exactly; at speed it strictly under-shoots V0 in the right direction.

## Skills

- `load-segments`, `score-model`, `pre-flight-final-model` — inspected metadata + bodies to understand the scoring contract and the grader schema. Could not invoke any because `python3` was sandboxed.
- `compare-models`, `visualise-segment`, `make-train-dev-split` — skipped; they require execution to add value.
- No skill was modified, extended, or deleted.

## Harness frictions encountered

- **`python3` denied.** Every attempt to run Python (one-liner, here-doc, script invocation) was blocked. I therefore could not run `score()` on V0 vs the new model, fit any per-platform gain, or even read the data schema beyond the CSV header. All numeric K_us values above are computed by hand from the parameter file.
- **REPORT.md write blocked** by the sub-agent filename filter. Content delivered as text in the parent response for manual persistence.

## Files in this bundle

- `predict.py` — exports `predict(sim_df, platform) -> DataFrame`.
- `manifest.json` — `platform_support`, `predict_callable`.
- `REPORT.md` — this file.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "m2-agent-05",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-05/final-model/REPORT.md",
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
