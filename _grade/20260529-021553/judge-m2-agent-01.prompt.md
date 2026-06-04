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
# Lateral-fidelity V2 — agent-01

## KPIs (own evaluation, all Ford segments under data/sim/segments)

|                            | Yaw RMSE (rad/s) | CTE RMSE (m) |
|---------------------------:|-----------------:|-------------:|
| V0 (KS baseline)           |          0.01479 |       151.99 |
| **V2 (this submission)**   |      **0.01113** |   **107.06** |

Per-platform:

| Platform                  |   V0 yaw |   V2 yaw |    V0 CTE |    V2 CTE |
|--------------------------:|---------:|---------:|----------:|----------:|
| FORD_F_150_LIGHTNING_MK1  |  0.01633 |  0.00582 |    157.51 |     64.45 |
| FORD_MUSTANG_MACH_E_MK1   |  0.01362 |  0.01368 |    148.00 |    128.84 |

Per-regime yaw RMSE (overall): straight 0.00945 → 0.00653, steady 0.02812 → 0.02085, transient 0.03825 → 0.03299.

Segment set: 415 Ford segments (175 F150 Lightning, 240 Mach-E). All segments were used for scoring; train/dev split (even/odd index on sorted sim.csv paths) was used only for coefficient fitting.

## Model

V2 = linear bicycle (Ackermann + understeer gradient) with steering-offset and first-order yaw-rate lag:

    y_ss[k] = v[k] · (delta[k] − delta0) / (L + K_us · v[k]²)
    y[k+1]  = y[k] + (dt/(tau+dt)) · (y_ss[k+1] − y[k])

Trajectory integrated with the same Euler / cumsum scheme the grader uses (`_shared/traj_metrics.integrate_trajectory`), so predicted (x, y) is consistent with the predicted yaw rate.

Coefficients fitted by Nelder-Mead on the deterministic train split, per platform; pooled per-sample SSE on v>3 m/s as the loss.

| Platform                  |     L  |       K_us | delta0 (rad) | tau (s) |
|--------------------------:|-------:|-----------:|-------------:|--------:|
| FORD_F_150_LIGHTNING_MK1  | 3.700  |  4.54e-03  |     +1.39e-3 |  0.060  |
| FORD_MUSTANG_MACH_E_MK1   | 2.984  |  8.61e-04  |     −2.45e-5 |  0.058  |
| TESLA_MODEL_3 (prior)     | 2.875  |  7.00e-04  |     0.0      |  0.080  |

Tesla has no truth channel in the data, so its coefficients are an uncalibrated literature-informed prior.

## What was tried

- **V1 — understeer + bias only.** Linearised in (K_us, delta0); OLS closed-form. Train-only: F150 yaw 0.0164 → 0.0068, Mach-E 0.0125 → 0.0124. Big F150 win, Mach-E flat.
- **V2 — V1 + first-order lag.** Joint Nelder-Mead fit. ~60 ms tire build-up time constant fitted on both Fords (consistent with cross-correlation lag of 3–5 samples at 50 Hz seen in train data). V2 is shipped.

## Skills used / modified / bypassed

- **score-model / score.py** — used as-is for scoring. Indispensable.
- **pre-flight-final-model / preflight.py** — used as-is. Confirms final bundle shape (8/9 pass, only REPORT.md missing because the sub-agent write guard blocks it).
- **load-segments, make-train-dev-split, compare-models, visualise-segment** — bypassed. Train/dev split is implicit (even/odd indices on sorted paths); loading and metrics done inline. Time-budgeted not to load each skill body.
- **_shared/traj_metrics.py** — read for integration scheme; I replicated the same Euler scheme inside `predict.py` to keep the bundle self-contained (no import of `_shared/` at grade time).

## Honesty notes

- Mach-E yaw RMSE shows a tiny regression on the full set (0.01362 → 0.01368). The signal-to-noise ratio at zero steering is bad on Mach-E (yaw std ≈ 0.011 rad/s at |delta|<0.005, v>5 — a noise floor any sample-level model cannot beat). V2 still wins Mach-E CTE by 13 % because the lag matches the *timing* of corner entry/exit, which is what trajectory integration rewards.
- Tesla numbers are uncalibrated. Tesla has no `yaw_rate_meas_rads` truth in this dataset so I could not validate them; the prior is just a placeholder so `platform_support` stays honest.

## What I'd want next

A stratified per-segment hold-out (speed × steering-magnitude bins), plus a fusion model that uses `a_lat_meas_mps2` to bound yaw-rate uncertainty (Kalman or a simple complementary filter). V2 ignores measured lateral accel entirely — that's the obvious next lever. And, of course, ground-truth yaw for Tesla.

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
