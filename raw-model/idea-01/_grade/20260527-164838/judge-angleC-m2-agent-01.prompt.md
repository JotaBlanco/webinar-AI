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

- agent_id: **angleC-m2-agent-01**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-2/agent-01/REPORT.md`

```markdown
# Module-2 / agent-01 (angle-C) — Lateral fidelity variant ladder

## Setup

- **Platform:** `FORD_MUSTANG_MACH_E_MK1` (315 segments, 913 626 samples @ 50 Hz). Tesla excluded — no decodable yaw-rate truth (rule 4).
- `yaw_rate_meas_rads` is the **measured** IMU yaw rate from the rlog; `yaw_rate_pred_rads` is KS-model output. Residuals follow team convention `pred − meas` (rule 1).
- **Operating contract (rule 5):** `v_mps` and `delta_road_rad` clamped to measured at every integrator step; only lateral states predicted.
- **Sign sanity:** `corr(δ_road, ψ̇_meas)` on cornering = **+0.701** → ISO-8855 holds (rule 2).
- **Train/test split:** every 5th sample → test, interleaved (rule 7). Test-set RMSEs reported.
- **Regime mask** (fixed): straight `|δ_road| < 0.5°`; transient (not straight ∧ 1-s rolling σ(δ_road) > 0.3°); else steady. Counts: straight 774k / steady 97k / transient 42k.
- **Accounting:** strict marginal V0→V4.

## Headline

**Yaw-rate RMSE 0.924 → 0.892 deg/s on test as a generalising per-platform fit (V2+V3), a 3.5% reduction. With per-segment calibration on top (V4) it falls to 0.792 deg/s (-14.3%), but that final hop is calibration, not model improvement (rule 8).**

## Variant ladder (yaw-rate RMSE, deg/s, test set)

| Variant | Fit scope | Overall | Δ vs prev | Straight | Steady | Transient |
|---|---|---|---|---|---|---|
| V0 baseline | n/a | 0.9244 | — | 0.4965 | 1.4251 | 3.0482 |
| V1 constant yaw bias | per-platform (1 scalar = +0.00075 rad/s) | 0.9248 | -0.0004 | 0.4945 | 1.4294 | 3.0524 |
| V2 steering-gain k | per-platform (k=1.0687, on top of V1) | 0.8927 | +0.0321 | 0.5336 | 1.3999 | 2.7406 |
| V3 lag align | per-platform (+1 sample = +20 ms) | 0.8895 | +0.0031 | 0.5322 | 1.4148 | 2.7058 |
| V4 per-segment bias | per-segment (315 scalars; calibration) | 0.7922 | +0.0973 | 0.3223 | 1.3809 | 2.6991 |

## a_y RMSE (m/s²) — re-derived per rule 9

| Variant | Overall | Straight | Steady | Transient |
|---|---|---|---|---|
| V0 | 0.338 | 0.311 | 0.491 | 0.379 |
| V1 | 0.335 | 0.307 | 0.491 | 0.379 |
| V2 | 0.363 | 0.331 | 0.557 | 0.349 |
| V3 | 0.363 | 0.331 | 0.558 | 0.354 |
| V4 | 0.345 | 0.309 | 0.549 | 0.357 |

## Per-variant interpretation

- **V0** unmodified residual. Errors dominated by transient cornering (3.05 deg/s).
- **V1 (≈ null)** Platform-level median residual is +0.00075 rad/s — dominated by 84% straight samples; both `pred` and `meas` near zero. No real lift.
- **V2 (per-platform steering gain k=1.069)** Fit by least squares on TRAIN. Big drop on transient (3.05 → 2.74, -10%); but **straight regresses** (0.50 → 0.53) — k>1 amplifies near-zero noise. The k>1 implies effective wheelbase is ~6% too large, or steering ratio is ~6% too low.
- **V3 (+20 ms lag)** Tiny but real on transients (2.74 → 2.71); steady regresses slightly. The optimal lag differs between regimes.
- **V4 (per-segment bias)** Biggest single jump, but **calibration, not model improvement** (rule 8). Straight-regime drop (0.53 → 0.32) is almost the entire effect: IMU mounting bias is a constant on straights.

## Regressions flagged

1. V2 hurts straight (0.497 → 0.534). Gain on near-zero predictor amplifies noise. Mitigation candidate: regime-conditional gain.
2. V2/V3 hurt `a_y` overall and in steady cornering (0.338 → 0.363). `a_y = v·ψ̇` coupling: scaling ψ̇ overshoots measured a_lat. The yaw and a_y channels disagree about which direction to scale — signature of structural KS limit (no slip angle).
3. V4 hurts a_y in steady (0.491 → 0.549) — same coupling.

## Painful absence

**Sub-agents / parallel evaluation.** Five variants × three regimes × two channels × cross-validation is embarrassingly parallel and I ran it serially. A sub-agent per variant with a shared scoring module would have surfaced V2's regime-conditional regression on straights an iteration earlier.

## Near-misses

- Rule 1 (`pred − meas`): had I assumed the inverse convention, I would have added the median bias and reported V1 as a win.
- Rule 7 (interleaved split): with a contiguous split V4's per-segment bias would have looked like a 0.2 deg/s lift because the same segment IDs would appear in train and test.
- Rule 8 (per-segment label): V4 is the biggest absolute drop; without the label I would have led with it.
- Rule 9 (re-derive a_y): catching the coupling exposed that V2/V3 regress a_y — a genuine finding.

## Surprise

V2's k=1.069 says the platform under-predicts yaw by ~7%. That's a wheelbase/steering-ratio mismatch in `PARAM_BY_PLATFORM` of the same scale — not noise, not slip — checkable against the openpilot `carParams` event. Yet V2 simultaneously worsens `a_y` in steady. The two truth channels disagree about how to scale, signature of a structural KS limit (no slip angle) rather than parameter error. Right next move isn't a third scalar, it's DST.

Files: `tools/`, `out/`.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleC-m2-agent-01",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-2/agent-01/REPORT.md",
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
