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

- agent_id: **angleA-m2-agent-03**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-2/agent-03/REPORT.md`

```markdown
# Module-2 / agent-03 — Lateral Fidelity Challenge

## Scoring setup

- **Platform scored**: `FORD_MUSTANG_MACH_E_MK1` (315 segments under `data/sim/segments/`).
- **Truth channels**: `yaw_rate_meas_rads`, `a_lat_meas_mps2` are measured (decoded from rlog IMU), not self-consistency.
- **Speed-known contract**: `v_mps` and `delta_road_rad` are inputs to the KS integrator (clamped at every step). The model's *predictions* are `yaw_rate_pred_rads` and `a_y_pred_mps2`. Speed and steering agreement is zero by construction and is not the metric.
- **Primary metric**: pooled-sample RMSE on `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` (rad/s).
- **Sign sanity**: `corr(delta_road_rad, yaw_rate_meas_rads) > 0` in 23/24 sampled segments. Left-positive convention confirmed.
- **Regime mask** (identical across every variant row):
  - *straight*: `|ψ̇_meas| < 0.05 rad/s`
  - *cornering transient*: `|ψ̇_meas| ≥ 0.05` and `|dψ̇_meas/dt| > 0.5 rad/s²`
  - *cornering steady*: `|ψ̇_meas| ≥ 0.05` and not transient

## Variants

- **V0 baseline** — `yaw_rate_resid_rads` from CSV, no preprocessing.
- **V1 per-segment bias removal** — subtract the per-segment mean of `(pred − meas)`. Targets IMU zero-rate offset and any δ-mounting bias.
- **V2 time alignment** — on top of V1, find integer-sample cross-correlation lag (search ±15 samples = ±300 ms) of `pred` vs `meas` and shift. Median fitted lag is +4 samples (~80 ms), pred leading meas — consistent with CAN/IMU report latency.
- **V3 understeer-gradient correction (isolated)** — `ψ̇_corr = ψ̇_pred / (1 + K_us · v²)`, with `K_us` fit globally by least squares against measured yaw rate on samples with `|ψ̇_meas| > 0.05` and `v > 3` m/s. Fitted **K_us ≈ 1.6 × 10⁻⁵ s²/m²** (very small).
- **V4 combo (V3 → V1 → V2 in that order)** — understeer correction, then per-segment bias on the corrected signal, then per-segment alignment.

## Results — pooled RMSE on `yaw_rate_resid_rads` (rad/s)

| variant | all (rad/s) | straight | cornering steady | cornering transient | marginal Δ on `all` |
|---------|------------:|---------:|-----------------:|--------------------:|--------------------:|
| V0      | 0.01613     | 0.00859  | 0.04237          | 0.08152             | —                   |
| V1      | 0.01414     | 0.00577  | 0.03965          | 0.07818             | -0.00198 (-12.3%)   |
| V2      | 0.01384     | 0.00556  | 0.03918          | 0.05578             | -0.00030 (-2.1%)    |
| V3*     | 0.01607     | 0.00848  | 0.04233          | 0.08164             | (isolated) -0.00006 |
| V4      | 0.01380     | 0.00547  | 0.03913          | 0.05587             | -0.00005 (-0.3%)    |

\* V3 is reported *isolated* against V0 (not sequential). Its sequential contribution inside V4 is captured in the V2→V4 row.

**Headline: V0 → V4 reduces pooled yaw-rate RMSE from 0.01613 to 0.01380 rad/s, a 14.5% drop. By regime: straight −36.4%, steady −7.6%, transient −31.5%.** The transient column is where the gain is concentrated in absolute terms.

## Attribution (accounting scheme: sequential marginal on `all`, isolated for V3)

- **V1 (bias removal): -0.00198 rad/s (85% of the V0→V4 drop).** Half of V0's RMSE in straight is a static IMU/integration bias.
- **V2 (alignment): -0.00030 rad/s on `all`, but -0.0224 rad/s on transient alone (-29%).** The "all"-regime headline understates this because transient samples are a minority of pooled time. Aligning pred by its median 80 ms lead matches transient cornering peaks much better.
- **V3 (understeer): -0.00006 rad/s isolated.** Fitted `K_us ≈ 1.6e-5 s²/m²` only matters at high `v²` (≈ 0.04 rad/s correction at 50 m/s). At Mach-E suburban speeds in this dataset the linear-bicycle understeer term is in the noise. **Not a regression but essentially a no-op at these speeds.** A full ST upgrade with proper slip dynamics (not an in-residual correction) would attack the remaining transient RMSE.

Marginal drops sum: 0.00198 + 0.00030 + 0.00005 = 0.00233 rad/s ≈ V0−V4 = 0.00233 rad/s. Accounting closes to round-off.

## Regressions

No variant worsened the metric. V3 nudged transient very slightly worse (0.08152 → 0.08164, +0.015%) because the global K_us fit overcorrects on a few high-yaw-rate samples — well within noise.

## Limitations

- Scored only Mach-E (315 segs), not F-150 Lightning (230 available).
- Lag fit is integer-sample at 50 Hz (20 ms resolution). A fractional-delay fit would shave a few % off transient.
- Per-segment IMU bias assumed constant; slow drift within a segment would alias into other variants.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleA-m2-agent-03",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-2/agent-03/REPORT.md",
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
