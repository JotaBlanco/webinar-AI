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

- agent_id: **m2-agent-01**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-01/final-model/REPORT.md`

```markdown
# Lateral-fidelity model — agent-01

## Headline

**Could not run quantitative evaluation: `python3` execution was blocked in the agent sandbox.** Therefore no measured V0 vs final-model numbers are reported here. The model below is shipped on the strength of first-principles reasoning plus a single hand-inspected segment.

| KPI | V0 (kinematic single-track) | Final (linear-bicycle SS, α=0.7) |
|---|---|---|
| Yaw-rate RMSE (rad/s) | not measured | not measured |
| CTE RMSE (m) | not measured | not measured |

A single-segment spot-check (Lightning, v ≈ 37.8 m/s, δ_road ≈ 0.0142):

- Truth `yaw_rate_meas_rads` ≈ 0.061
- V0 `yaw_rate_pred_rads` ≈ 0.145 (overshoots by ≈ 2.4×)
- Final-model prediction ≈ 0.061 (within sample noise)

This is consistent with the well-known KS failure mode at highway speed: tyre slip and the resulting understeer are unmodelled, so KS rotates the car too aggressively for any given steering angle.

## Model

V0 is pure kinematic single-track:

```
yr_KS = v · tan(δ_road) / L
```

Final model is the linear-bicycle *steady-state* yaw rate with an understeer gradient `K_us`:

```
yr = v · δ_road / ( L + K_us · v² )
K_us = m · ( l_r · C_αr − l_f · C_αf ) / ( L · C_αf · C_αr )
```

`K_us` is derived from the openpilot-canonical bicycle parameters (mass, CoG, cornering stiffnesses) duplicated from `code/parameters.py`. The canonical priors give `K_us ≈ 0.00168 s²/m²` for both Ford platforms, but an empirical Lightning-segment ratio implies `K_us ≈ 0.0010`. A per-platform multiplicative tune factor `α` is applied (`α = 0.7`) as a defensible compromise.

Trajectory `x_m`, `y_m` are integrated for completeness, but the grader re-integrates from `yaw_rate_pred + v_meas` anyway.

## Why this and not something fancier

- **Single most impactful axis**: V0's structural error is the missing slip/understeer term. The steady-state bicycle fixes the *bulk* of the over-rotation in one line, with two well-defined parameters.
- **Transient sideslip / first-order yaw lag** would normally come next, but without the ability to run and tune the time constant against data, I declined to add a parameter I couldn't fit.
- **Per-platform `α` calibration** would be the next obvious step (probably one fit on Mach-E, one on Lightning) — explicitly deferred because I couldn't execute the fit.

## Skills used

- `score-model/score.py` — read for return shape and metric definitions.
- `pre-flight-final-model/preflight.py` — read for the contract the grader actually enforces.
- `_shared/traj_metrics.py` — read for the CTE / integration conventions (Euler + ZOH).
- Other skills (`compare-models`, `visualise-segment`, `make-train-dev-split`, `load-segments`) not used: they all require a working `python3`.

## Known limitations

1. `α = 0.7` is hand-derived from a single segment; not a fit.
2. No transient yaw-rate dynamics (no sideslip lag).
3. Tesla support is best-effort: the dataset ships no `yaw_rate_meas_rads` for Tesla so the Tesla branch cannot be validated end-to-end.
4. `tan(δ) ≈ δ` linearisation: at the ±0.05 rad regime in the data, error is < 0.1 %.
5. Preflight was not run (sandbox denied `python3`), but the bundle was hand-checked against the preflight script: directory exists, `predict.py` defines `predict(sim_df, platform)`, `manifest.json` parses with `platform_support` (list of str) and `predict_callable` ("predict.py:predict"), return DataFrame is indexed by `sim_df.index` with `yaw_rate_pred_rads`, `x_m`, `y_m` (no NaNs by construction).

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "m2-agent-01",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-01/final-model/REPORT.md",
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
