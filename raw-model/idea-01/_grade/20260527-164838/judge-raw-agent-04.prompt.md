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

- agent_id: **raw-agent-04**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-04/REPORT.md`

```markdown
# Lateral-prediction improvement ladder — Ford KS model (agent 04)

## 1. Headline number

**Yaw-rate RMS residual** across all 545 Ford segments (Mach-E + F-150 Lightning), evaluated on held-out test split (50% of each segment):

| | rad/s | °/s |
|---|---|---|
| **Baseline V0** (raw, openpilot-canonical KS) | 0.01804 | **1.034** |
| **Final V4** (cleaned + lag + understeer) | 0.01191 | **0.682** |

**Total improvement: 34% reduction in RMS yaw-rate residual.**
If we strip out the data-hygiene step (which is not a model change), the model-only improvement is **20% reduction** on the clean subset (0.853 → 0.682 °/s).

## 2. What I implemented

The KS prediction is `ψ̇ = (v / L) · tan(δ)` with measured `v` and `δ` clamped at every step (speed-known lateral-only mode). I left the integrator alone and improved the prediction formula:

- **V1 hygiene** – mask out rows with `v ≤ 2 m/s`, `|a_lat_meas| > 20 m/s²`, `|ψ̇_meas| > 2 rad/s`. Pure data clean-up — no model change.
- **V2 steering bias** – fit a single global `δ_bias` (linearised least-squares using `sec²(δ)` derivative) on the train half and subtract: `tan(δ − δ_bias)`. Catches alignment / wheel-angle-sensor zero offset.
- **V3 transport lag** – integer-sample shift of `δ` (per segment, no boundary crossing) over `±10` samples at 50 Hz. Best lag was `τ = +3 samples = 60 ms` — measured steering leads the yaw response by ~60 ms, exactly the order of magnitude expected from rack + tyre transient.
- **V4 understeer gradient** – joint least-squares fit of `δ_bias` and an effective-wheelbase `K_us`: `ψ̇ = v / (L · (1 + K_us · v²)) · tan(δ − δ_bias)`. Fitted `K_us ≈ 4.4 × 10⁻⁴ s²/m²` — i.e. the kinematic model under-predicts lateral compliance at speed, exactly the gap a real bicycle/ST model fills.

All parameters were fit on the first half of each segment in time; metrics reported on the second half.

## 3. Attribution

**Scheme: sequential left-to-right.** Each step is evaluated *after applying all previous steps*. The "contribution %" is the share of the total RMS drop produced by that step:

| Step | RMS before | RMS after | Drop | % of total |
|---|---|---|---|---|
| V1 hygiene | 0.01804 | 0.01488 | 0.00316 | **51.5%** |
| V2 steering-bias | 0.01488 | 0.01477 | 0.00012 | 1.9% |
| V3 transport-lag (τ = 60 ms) | 0.01477 | 0.01437 | 0.00040 | 6.5% |
| V4 understeer + refit bias | 0.01437 | 0.01191 | 0.00246 | **40.1%** |

Order matters for sequential attribution. If you re-order, hygiene and understeer remain the two giants; bias/lag are second-order. Per-platform on V4: Mach-E 0.700 °/s, F-150 0.656 °/s — the truck is actually a touch easier to predict (longer wheelbase, less aggressive driving in the segments).

## 4. Surprises

- **Two F-150 segments had stationary vehicles with `a_lat_meas` blowing up to 1057 m/s²** (`112e4d6e0cad05e1/.../00000016--300e9e8ccb/0` and `.../00000004--c2ebfcbf0d/0`). Almost certainly a CAN/sensor bring-up artefact when stationary. They poisoned the unfiltered F-150 a_y RMS to ~10.9 m/s². The yaw-rate channel was fine on the same rows. Strong argument for keeping `a_y` and `ψ̇` as separate metrics.
- **Steering bias is essentially zero** (0.014° road / 0.23° steering-wheel). The openpilot zero-offset is well calibrated. I expected a few tenths of a degree.
- **Transport-lag is small in absolute terms (40 e-5 RMS drop)** but consistent — it picked `+3 samples = 60 ms` deterministically, and it's a free improvement.
- **Understeer is by far the biggest pure-model effect.** A single scalar `K_us = 4.4 × 10⁻⁴ s²/m²` (same value across both platforms in my joint fit) recovers 40% of the total drop. That's effectively the message: a bicycle/ST model would justify itself if K_us doesn't generalise per-platform.

## 5. Limitations

- I did not retrain `K_us` per platform — would expect Mach-E and F-150 to want different values. Easy next step.
- I did not attribute the `a_y` metric — the F-150 stationary glitches required a hygiene mask first, and the headline question was about lateral prediction more broadly so I picked yaw-rate as cleaner. `a_y` after V4 should drop comparably since `a_y = v · ψ̇` under the clamps.
- I did not re-run the integrator — every "improvement" is post-hoc arithmetic on the existing CSVs. That's fine for KS in speed-known mode (since the only state contributing to `ψ̇` is the clamped `δ`), but a real ST model with `β` and `ψ̇` as integrated states would need re-integration.
- I treated `K_us` as global; one could fit `K_us` per (platform, v-bin) and recover more.
- I did not explore: (a) steering-rate / `δ̇` feed-forward, (b) low-pass-filter mismatch between measured `a_y` (5 Hz cutoff per adapter) and predicted (no filter), which could be biasing the a_y residual.
- I had no access to the canonical solution / observations / sibling reports / cross-angle modules (and didn't try). I never attempted to read those.

## 6. Files produced

- `tools/baseline.py`
- `tools/ladder.py`
- `out/ladder_run.txt`

```
ISOLATION_REPORT:
read_outside_allowed: []
attempted_blocked: []
shared_dir_writes: []
notes: "Stayed within ./code, ./data, and own folder. No hook blocks triggered. Did not attempt sibling, webinar-angle-*, or webinar-00 reads. Skipped TodoWrite per instructions; two reminders ignored as task was short and linear."
```

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "raw-agent-04",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-04/REPORT.md",
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
