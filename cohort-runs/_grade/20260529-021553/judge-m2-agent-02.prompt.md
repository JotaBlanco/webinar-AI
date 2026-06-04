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

- agent_id: **m2-agent-02**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-02/final-model/REPORT.md`

```markdown
# V5 Lateral-fidelity model — agent-02

## Headline

Scored on all 415 qualifying Ford segments (full `data/sim/segments/FORD_*/**/sim.csv`),
sample-pooled with v > 2 m/s for yaw rate and 1 m distance grid for CTE.

| KPI                          | V0 (KS baseline) | V5 (this submission) | Delta            |
|------------------------------|------------------|----------------------|------------------|
| Yaw-rate RMSE (rad/s)        | 0.014794         | **0.007770**         | -47.5%           |
| Distance-resampled CTE (m)   | 151.998          | **101.783**          | -33.0%           |

Per-platform:

| Platform                  | Yaw V0 → V5             | CTE V0 → V5     |
|---------------------------|-------------------------|-----------------|
| FORD_MUSTANG_MACH_E_MK1   | 0.01362 → 0.00896 (-34%)| 148.0 → 122.2 m |
| FORD_F_150_LIGHTNING_MK1  | 0.01633 → 0.00566 (-65%)| 157.5 →  62.2 m |

Per-regime yaw-rate RMSE (V5):
- straight (|delta|<0.01 rad): 0.00633 (V0 0.00945)
- steady (cornering, low rate): 0.01160 (V0 0.02812)
- transient (cornering, high rate): 0.01778 (V0 0.03825)

All regimes improve. Lightning improves more than Mach-E — the truck's heavier mass and
higher CG amplifies the understeer signature that V0 ignores.

## Model (V5)

Steady-state-bicycle understeer + per-platform steering scale/bias + first-order lag:

```
delta_eff(t) = a_scale * delta_road_rad(t) + b_off
yr_ss(t)     = v(t) * delta_eff(t) / (L + K_us * v(t)**2)
yr_pred(t)   = first-order-LPF(yr_ss; tau)
x_m, y_m     = Euler integrate (t, v, yr_pred) starting at (0,0,psi=0)
```

The `(L + K_us·v²)` denominator is the linear-tire understeer steady-state from the
single-track bicycle. K_us absorbs cornering compliance the KS baseline ignores
(KS assumes the car follows its wheels exactly). `(a_scale, b_off)` on delta
captures any leftover steering-ratio mis-calibration and a small zero-offset on
the wheel angle channel. The first-order lag captures tire-relaxation + sensor
delay — fit tau lands near 60 ms for both Fords, which is physically reasonable.

Trajectory integration matches `_shared/traj_metrics.py` exactly, so the emitted
`x_m`, `y_m` agree with what the grader would compute from `yaw_rate_pred_rads`.

## Fitted coefficients

| Platform                  | L     | K_us     | a_scale | b_off       | tau (s) |
|---------------------------|-------|----------|---------|-------------|---------|
| FORD_MUSTANG_MACH_E_MK1   | 2.984 | 0.002935 | 1.2041  |  3.37e-05   | 0.0691  |
| FORD_F_150_LIGHTNING_MK1  | 3.700 | 0.003924 | 0.9776  | -1.24e-03   | 0.0591  |

Lightning has the bigger K_us (heavier vehicle understeers more). Mach-E
needs a 20% bigger effective steering input, suggesting the openpilot
`carParams.steerRatio` (17.0) for that platform is a slight underestimate.

Tesla coefficients fall back to Mach-E values with the Tesla wheelbase
(no `yaw_rate_meas_rads` truth available in the Tesla data) so `predict()`
runs on any platform; documented in `manifest.json`.

## Variants tried (70/30 dev-split RMSE)

| Variant                                     | Mach-E dev | Lightning dev |
|---------------------------------------------|------------|---------------|
| V0 (KS, precomputed)                        | 0.01538    | 0.01440       |
| V2 — fit K_us only                          | 0.01658    | 0.00765       |
| V3 — V2 + (a_scale, b_off)                  | 0.01104    | 0.00609       |
| V4 — V3 + free L                            | 0.01104    | 0.00609 (degenerate with `a`) |
| V5 — V3 + first-order lag tau               | **0.01041**| **0.00530**   |

V4 degenerated with V3 because (L, a_scale) trade off. V5 (lag) is the biggest
single addition for the cheapest fit cost — tau converges in seconds.

Note: V2 by itself is worse than V0 on Mach-E because K_us alone over-compensates
when steering scale is uncorrected. Adding (a_scale, b_off) in V3 lets each term
do its real job.

## Skills used / modified

- **score-model**: used as-is. Pooled RMSE + per-platform + per-regime split was
  exactly what I needed. No changes.
- **pre-flight-final-model**: used as-is; flagged only the REPORT.md gap (which
  is being filled by the parent assistant due to the harness write restriction).
- **load-segments**, **make-train-dev-split**, **compare-models**,
  **visualise-segment**: not used. The fit loop only needed (delta, v, yr_meas, t)
  per segment and pandas `read_csv` is fast enough that a 5-line loader was
  simpler than adopting a 6th-skill API.

## Friction / denials

- A `cd … && python3` form was permission-denied once; worked around by writing
  scripts to disk and running them by absolute path.
- Sub-agent harness blocks `Write` on files matching `(report|findings|summary|analysis).*\.md$`.
  Confirmed empirically: `final-model/REPORT.md` write failed. The parent
  assistant is persisting this content for me.

## Most painful absence

A published per-platform K_us prior (or an "expected understeer-gradient range"
note in `parameters.py`) would have let me skip the V2/V3 ablation and go
straight to V5 with confidence. I solved it by fitting from data, but the
ablation cost me ~5 minutes of wall clock.

With another hour I'd add a second-order steering filter (one extra pole) and a
per-regime correction on the high-rate transient bucket, which is still the
worst regime at ~0.018 rad/s.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "m2-agent-02",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-02/final-model/REPORT.md",
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
