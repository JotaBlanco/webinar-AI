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

- agent_id: **m2-agent-04**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-04/final-model/REPORT.md`

```markdown
# agent-04 — lateral-fidelity final model

## Headline

Could not produce empirical KPI numbers because `python3` execution was denied inside this working folder for the entire session. The model below is a defensible analytic upgrade over V0 and is shipped with no fabricated benchmark results.

## What I implemented

**V1 — Linear-bicycle steady-state with understeer gradient.**

Yaw-rate prediction:

    yaw_rate = v * tan(delta) / ( L + K_us * v^2 )

V0 is the special case K_us = 0. `K_us` is derived analytically from the ST-rung openpilot-canonical parameters in `code/parameters.py`:

    K_us = (m / L) * ( l_r / C_alpha_f  -  l_f / C_alpha_r )

| Platform                  | L (m) | K_us (rad/(m/s²)) |
|---------------------------|-------|-------------------|
| TESLA_MODEL_3             | 2.875 | 0.001677          |
| FORD_MUSTANG_MACH_E_MK1   | 2.984 | 0.001677          |
| FORD_F_150_LIGHTNING_MK1  | 3.700 | 0.001678          |

The three values cluster: comma.ai's canonical ST parameters imply a near-identical steady-state cornering response across the fleet. This is itself a quiet sanity check on the priors.

### Expected sign of improvement

V0 systematically *over*-predicts yaw rate in any cornering regime where lateral acceleration is non-trivial (i.e., the tyres are doing work). The understeer correction pulls predicted yaw rate down proportionally to v², which:

- Leaves V0 essentially unchanged at low speed (where v² is small and V0 is already accurate).
- Leaves V0 essentially unchanged on straights (delta ≈ 0).
- Pulls V0 down on high-speed sweepers — the regime V0 most over-predicts.

So we expect headline yaw-rate RMSE to drop, with the gain concentrated in the `steady` and `transient` non-straight regimes. CTE RMSE should fall because trajectory error accumulates from yaw-rate error.

### Trajectory

`x_m, y_m` are produced by re-using exactly the Euler integration scheme the grader applies in `_shared/traj_metrics.integrate_trajectory` (zero-order hold, starting from (0, 0, 0)). Reproducing the scheme inside `predict.py` guarantees that the integration is not a source of mismatch between our trajectory and the truth trajectory the grader builds.

## What I did NOT implement (and why)

- **Per-platform fit of K_us.** No Python execution available to optimise. The analytic K_us is the next-best thing and is parameter-free.
- **Transient (first-order-lag) yaw response.** This would need a tunable time constant and per-platform validation; not safe blind.
- **Steering-bias / scale correction.** Same reason. Without empirical fit it can easily make things worse.
- **Per-regime blending of V0 and V1.** Without evaluation we can't justify it; V1 reduces to V0 at low speed by construction anyway.

## Skills used / modified / bypassed

| Skill                       | Used? | Notes                                        |
|-----------------------------|-------|----------------------------------------------|
| `load-segments/`            | read  | Read source to confirm path/column conventions. |
| `score-model/`              | read  | Read source to confirm RMSE/CTE definitions; could not execute. |
| `compare-models/`           | no    | Could not execute without Python.            |
| `visualise-segment/`        | no    | Could not execute without Python.            |
| `make-train-dev-split/`     | no    | No training needed for analytic V1.          |
| `pre-flight-final-model/`   | read  | Read source to ensure shape contract met.    |
| `_shared/traj_metrics.py`   | read  | Reproduced its Euler integration in `predict.py`. |

No skill was modified or deleted; none would have helped if I couldn't run Python.

## Harness / isolation friction

The single blocker was that `python3` execution was denied inside the agent working directory (and from the parent directory) for every attempt during this session. That denied me access to every scoring, comparison, and pre-flight skill. The final model was therefore engineered from parameter sheets + the model equations alone.

`Write` on `REPORT.md` was also blocked by the sub-agent harness as the task brief anticipated; this content is returned in the final response for the parent to persist.

## Most painful absence

Ability to run `python3` against `skills/score-model/score.py`. Without it, I could not measure the V0 baseline numerically, could not tune K_us, could not check the per-regime breakdown, and could not run the pre-flight shape check. Everything else (data structure, parameters, integration scheme) was available via file reads.

## Deliverable layout

- `predict.py` — `predict(sim_df, platform) -> DataFrame` exporter.
- `manifest.json` — `platform_support`, `predict_callable = "predict.py:predict"`.
- `REPORT.md` — this file (persisted by parent because sub-agent Write was blocked).

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "m2-agent-04",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-04/final-model/REPORT.md",
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
