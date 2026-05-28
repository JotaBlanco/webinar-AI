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

- agent_id: **angleB-m2-agent-05**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-2/agent-05/REPORT.md`

```markdown
# Module-2 / agent-05 (angle-B) — Lateral fidelity variant ladder

## Scope and contract

- **Platform scored:** `FORD_MUSTANG_MACH_E_MK1` (305 of 315 segments used; 10 too short or missing columns).
- **Truth column:** `yaw_rate_meas_rads` — measured by the Ford chassis IMU, decoded via `opendbc/ford_lincoln_base_pt`. Not predicted, not self-consistency.
- **Clamped (inputs):** `v_mps`, `delta_road_rad` (per `clamp_v_to_measured=True, clamp_delta_to_measured=True`).
- **Predicted (under test):** `yaw_rate_pred_rads = (v/L)·tan(δ)`. Residual = pred − meas.
- **Regime mask** (shared across all variants): `v > 5 m/s`; straight `|δ| < 0.01 rad`; transient `|d(yaw_meas)/dt| > 0.5 rad/s²` on cornering; steady = remainder of cornering.

## Variant ladder — RMSE of `yaw_rate_resid_rads` (rad/s)

| Variant | Description | Overall | Straight | Steady cornering | Transient cornering | Marginal drop (vs prev) |
|---|---|---:|---:|---:|---:|---:|
| V0 | Baseline (`yaw_rate_resid_rads` as-is) | 0.01161 | 0.00923 | 0.02281 | 0.08360 | — |
| V1 | + per-segment yaw-rate bias removal | 0.00891 | 0.00517 | 0.02215 | 0.08422 | -0.00270 |
| V2 | + understeer-gradient correction `K_us·ψ̇_pred·v²` fit per segment on steady cornering | 0.00782 | 0.00648 | 0.01401 | 0.06997 | -0.00109 |
| V3 | + first-order steering actuator lag τ on δ before recomputing KS yaw | **0.00714** | 0.00626 | 0.01204 | **0.03528** | -0.00068 |

**Total V0 → V3 drop = 0.00447 rad/s (38% of V0).** Sum of marginals = 0.00447 (perfect closure, well inside the 15% tolerance). **Accounting scheme: forward-incremental marginal** — each row's drop equals `RMSE(V_{i-1}) − RMSE(V_i)`, in ladder order.

## Fitted parameters (median across segments)

- bias = +0.00166 rad/s (gyro zero / steering centre offset).
- K_us = +0.0 s²/m² median, but heavy-tailed: segments with real steady cornering picked up positive K_us in the 0.003–0.01 range, hence the big steady-regime drop.
- τ = 0.10 s (steering actuator lag).

## Regression noted

V1 slightly worsens the transient regime (0.0836 → 0.0842, +0.7%). Cause: bias fit on straight samples nudges genuine signed yaw-rate energy in the wrong direction in transients. V2 and V3 more than reclaim this.

## Surprise

**V3's tail-crushing effect on transients.** τ=0.10 s first-order lag alone cuts transient RMSE 0.070 → 0.035 (50%). KS wasn't wrong about the steady relationship — it was wrong about *when* the yaw rate happens. Much cheaper, more interpretable fix than going to a full ST tyre model. Suggests at least half of what we'd previously attributed to "missing slip dynamics" is actually missing actuator dynamics.

## Painful absence

Tesla has 1025 segments but no decoded IMU truth — two-thirds of the corpus invisible to lateral fidelity work. Ford fleet small (315 + 230) and Mustang-heavy.

## Rule-prevented near-misses

- "Do not unclamp v/δ" — saved me from letting the integrator close its own loop.
- `delta_road_rad` vs `delta_wheel_deg` (factor of 17 in K_us).
- "V0 as-is, no preprocessing" — was tempted to fold V1 bias into V0.
- Parameters from `PARAM_BY_PLATFORM` (L=2.984 m).

Files: `out/analyze.py`, `out/ladder.csv`, `out/fit_summary.txt`.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleB-m2-agent-05",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-2/agent-05/REPORT.md",
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
