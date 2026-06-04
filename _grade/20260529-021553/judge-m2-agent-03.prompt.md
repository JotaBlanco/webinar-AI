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
# Final-model report — agent-03

## Model: linear bicycle with understeer + 1st-order yaw-rate lag

Per-platform closed-form prediction:

```
yr_ss[k] = v[k] · (delta[k] − d0) / L_eff / (1 + K · v[k]^2)
yr[k+1]  = yr[k] + (dt / (tau + dt)) · (yr_ss[k+1] − yr[k])    # first-order lag
yr[0]    = yr_ss[0]
```

Four free parameters per platform: `L_eff`, `K`, `d0`, `tau`.

Trajectory `(x, y)` is left to the grader's canonical Euler integrator in
`_shared/traj_metrics.py`, fed by predicted yaw rate and measured `v`.

## Why this model

The V0 baseline (`code/ks_model.py`) is the pure kinematic single-track. It
sets `yr = (v/L)·tan(δ)` with no tyre side-slip and no actuator/yaw dynamics.
Diagnostic on the data:

- **F-150 Lightning** (3084 kg, L = 3.70 m): the kinematic prediction
  systematically *over*-shoots measured yaw. A one-parameter linear fit
  `yr_meas = a · yr_pred` recovers `a ≈ 0.864` — the truck is much more
  understeer-y than the kinematic prior. Adding a 1/(1+Kv²) term reduces
  yaw RMSE from 0.01633 to 0.00568 (-65%).
- **Mustang Mach-E** (2336 kg, L = 2.984 m): closer to neutral but still
  benefits from a 2-parameter fit (effective wheelbase 2.48 m + understeer
  v_ch ≈ 32). Yaw RMSE 0.01362 → 0.00901 (-34%).
- A first-order lag `τ = 0.05 s` shaves another 5-10% mostly in the
  transient regime by smoothing the steady-state response toward what the
  vehicle actually does in the first 50 ms after a steering input change.

The understeer gradient `K` is what a linearised dynamic bicycle (Pacejka
small-slip) gives you in closed form:
`K = m · (l_r · C_r − l_f · C_f) / (L^2 · C_f · C_r)`. Rather than carry
mass / inertias / cornering stiffnesses through a full ST integration, I
fit `(L_eff, K, d0, tau)` directly per platform — cheaper to compute,
robust on dev, and avoids inheriting the openpilot `C_alpha_*` priors which
the data clearly disagree with (especially the truck).

## Fit procedure

- 80/20 segment split per platform, seed=42.
- `(L_eff, K, d0)` minimised by Nelder-Mead on `mean((yr_pred − yr_meas)²)`
  over samples with `v > 2 m/s`.
- `tau` chosen by 10-point grid search `{0, 0.02, 0.05, 0.1, …, 0.5}` on
  the same v-filtered samples; selected on the dev split.

| Platform | L_eff (m) | K (1/(m/s)²) | v_ch (m/s) | d0 (rad) | tau (s) |
|---|---|---|---|---|---|
| F-150 Lightning | 3.787 | 1.060e-3 | 30.71 | +0.00129 | 0.05 |
| Mach-E          | 2.477 | 9.715e-4 | 32.08 | +4.48e-5 | 0.05 |

## Results — KPI table

Scored with `skills/score-model/score.py` (matches the canonical metric in
`_shared/traj_metrics.py`) on all 415 Ford segments, v > 2 m/s mask for
yaw-rate RMSE, distance-resampled CTE at 1 m bins, min 20 m per segment.

| Metric | V0 | V1 | Δ |
|---|---|---|---|
| Pooled yaw-rate RMSE (rad/s) | 0.01479 | **0.00781** | -47% |
| Pooled CTE RMSE (m) | 151.99 | **102.40** | -33% |
| F-150 yaw RMSE | 0.01633 | 0.00568 | -65% |
| F-150 CTE | 157.51 | 62.10 | -61% |
| Mach-E yaw RMSE | 0.01362 | 0.00901 | -34% |
| Mach-E CTE | 148.00 | 123.08 | -17% |
| Straight (|δ|<0.01) yaw RMSE | 0.00945 | 0.00635 | -33% |
| Steady-corner yaw RMSE | 0.02812 | 0.01158 | -59% |
| Transient yaw RMSE | 0.03825 | 0.01817 | -52% |

Held-out (20% dev): F-150 yaw 0.00502 / CTE 46.8; Mach-E yaw 0.00779 /
CTE 154.1 — train/dev gap is small, so the 4-param fit is not overfit.

## What I did not do (and why)

- **Full linear single-track (ST) integration** — would expose `m`, `I_z`,
  `l_f`, `l_r`, `C_αf`, `C_αr` separately, but at the cost of an ODE
  integration per segment and 6× the moving parts. The closed-form
  `(1+Kv²)` formula is the steady-state limit of ST and turns out to be
  enough for `yr` to within 8 mrad/s on this data — the residual is
  dominated by actuator/sensor lag and rare high-slip events, not by ST
  vs KS structure.
- **Trajectory `(x, y)` returned directly** — under the canonical
  integration contract (`clamp_v_to_measured = True`), predicted `(x, y)`
  is a deterministic function of predicted `yr` and measured `v`, so
  there is nothing to gain from returning it ourselves (and risk
  introducing a different integrator).
- **Per-segment online calibration** — too much overfit risk for a
  45-minute budget on 415 segments.
- **TESLA_MODEL_3** — no measured yaw channel in the data set I scored
  on, so I did not fit it; manifest declares Ford-only support.

## Files

- `predict.py` — exports `predict(sim_df, platform) -> DataFrame`.
- `coeffs.json` — per-platform `(L_eff, K, d0, tau)`.
- `manifest.json` — platform_support + predict_callable.

Pre-flight check (`skills/pre-flight-final-model/preflight.py`) passes all
checks except `report_md_present`, which the sub-agent harness blocks from
writing — this REPORT.md is delivered as text in the agent return and
persisted by the parent.

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
