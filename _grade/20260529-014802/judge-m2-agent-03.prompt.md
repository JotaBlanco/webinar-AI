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

- agent_id: **m2-agent-03**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-03/final-model/REPORT.md`

```markdown
# agent-03 — Lateral fidelity, V1

## TL;DR

Replace the kinematic single-track (KS) yaw-rate output with the **linear bicycle steady-state** expression, parameterised by the openpilot-canonical ST-rung values for each Ford platform. One-line model, no fitting, no time-constants — just the textbook understeer gradient.

```
V0 (baseline):  yr = (v / L) * tan(delta_road)         # KS, no slip
V1 (this):      yr = v * delta_road / (L + K_us * v^2) # linear bicycle
                K_us = m * (l_r*C_r - l_f*C_f) / (L * C_f * C_r)
```

At v = 0 the two agree (Ackermann). At highway speed (v ~ 30 m/s), V0 over-predicts yaw rate by ~30-40 % because it ignores tyre slip — that is the residual energy V1 reclaims.

## Why this and not something fancier

A linear bicycle ODE with first-order steering lag (`tau * dyr/dt + yr = yr_ss`) is the next rung. With the harness denying me Python execution (see below) I cannot fit `tau`, and shipping a guessed time constant carries real risk of making transient regions worse than V0. The steady-state V1 is monotonic-safe: in steady cornering (the largest contributor to cumulative CTE on these segments) it is unambiguously closer to the truth than V0; in transients it is no worse, and arguably better because the magnitude is right even if the phase is uncorrected.

## Computed K_us per platform (sanity)

| Platform | L (m) | K_us (s^2/m^2) | Correction at v=25 m/s |
|---|---|---|---|
| Ford Mustang Mach-E MK1 | 2.984 | 0.001676 | L / (L+K_us*v^2) = 0.74 |
| Ford F-150 Lightning MK1 | 3.70 | 0.001677 | 0.78 |
| Tesla Model 3 | 2.875 | 0.001678 | 0.73 |

The three platforms land in the same understeer-gradient band — consistent with the openpilot tuning philosophy across these vehicles — so the V1 fix is broadly applicable without per-platform retuning.

## Headline numbers

I was **denied `python3` execution** by the harness, so I could not run `skills/score-model` against my data to produce empirical RMSE numbers. Every KPI claim in this report is a derivation, not a measurement. Expected direction: V1 should beat V0 on both yaw-rate RMSE and distance-resampled CTE RMSE on Ford segments, with the largest gains in high-speed steady-cornering regimes (where the V0 bias is largest and CTE accumulates fastest).

I was also unable to run `skills/pre-flight-final-model/preflight.py`. The bundle layout however matches the contract that script encodes (verified by reading `preflight.py`): `predict.py` present, `manifest.json` with both required fields, `REPORT.md` > 100 bytes, `predict(sim_df, platform)` accepts two positional args and returns a DataFrame with `yaw_rate_pred_rads` aligned to `sim_df.index`.

## What I implemented

- **V1**: `predict.py` returns the linear-bicycle steady-state yaw rate. Self-contained — ST parameters are mirrored from `code/parameters.py` so the grader does not need access to the workshop code tree.
- Did not supply `x_m` / `y_m`: lets the grader integrate trajectory with its canonical scheme in `_shared/traj_metrics.py`, eliminating any chance of an integrator-mismatch penalty.

## Skills used / modified / bypassed

- Used (read-only, for spec): `score-model/score.py`, `pre-flight-final-model/preflight.py`, `load-segments/load.py`, `_shared/traj_metrics.py`.
- Bypassed: `compare-models`, `visualise-segment`, `make-train-dev-split` — no fitting, no comparison runs, no plots needed for a closed-form one-liner.
- Modified: none. With Python execution blocked, modifying skills would have no operational value.

## What the harness denied that mattered

`python3 ...` calls were refused. That ruled out:
1. Measuring V0 vs V1 RMSE on the actual segments.
2. Running preflight before declaring done.
3. Any kind of tau / steering-offset fit (would need scipy.optimize).

## Most painful absence

Numeric scoring. With one `python3 score.py` I could quote real numbers, back the V1-vs-V0 claim with data instead of theory, and confidently try a two-parameter fit (tau, delta_offset) for an even bigger jump. Without it, shipping anything beyond the textbook closed-form is gambling.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "m2-agent-03",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-03/final-model/REPORT.md",
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
