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

- agent_id: **agent-07**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-07/REPORT.md`

```markdown
# Lateral-prediction improvements — KS model, Ford corpus (agent-07)

**Headline metric**: RMS yaw-rate residual (deg/s), aggregated across **545 Ford segments / 1,580,767 samples** at 50 Hz from both `FORD_MUSTANG_MACH_E_MK1` and `FORD_F_150_LIGHTNING_MK1`. (Tesla has no measured yaw-rate truth channel in the CSVs, so it's excluded.)

| Variant | RMS (deg/s) |
| --- | --- |
| **V0 baseline KS (as stored)** | **1.0336** |
| **V4 final (full ladder)** | **0.7401** |

→ **28.4 % reduction**. Holdout split (70/30 by segment, fits learned on train only): on the Mach-E test set V0→V3 is 0.660 → 0.393 deg/s (-40 %); on the F-150 test set 1.386 → 1.057 deg/s (-24 %). The per-platform gains and understeer coefficient generalise out of segment, so the improvement is not just overfitting.

## What I implemented

The KS lateral prediction is `psi_dot = (v / L) · tan(δ_road)` with `δ_road = δ_wheel / i_s`. My ladder layered one knob at a time on top of that:

- **V1 — per-segment steering-angle bias.** Fit one DC offset `b` per segment so that `(v/L)·tan(δ - b)` minimises RMS yaw residual. Closed-form linear LS via the `sec²(δ)·b` linearisation. P95 of `|b|` is 3.1° at the steering wheel — typical sensor zero-offset.
- **V2 — per-platform yaw-rate gain `k`.** Replace prediction with `k·(v/L)·tan(δ−b)`. Mach-E k = 1.073 (effective steering ratio 17.0 → 15.85); F-150 k = 0.872 (16.9 → 19.38). The fact that the two platforms move in opposite directions tells you the carParams `steerRatio` isn't the real-world effective number for either.
- **V3 — understeer gradient `K_us`.** Swap in the linear-bicycle yaw-rate gain: `psi_dot = v·δ_eff / (L + K_us·v²)`. Fit one `K_us` per platform on top of V2's effective angle. Both platforms come out near `K_us ≈ 0.0011` (characteristic speed ≈ 53 m/s ≈ 190 km/h) — modest, consistent neutral understeer.
- **V4 — per-platform steering-to-yaw lag.** Integer-sample search ±10 samples (±200 ms) at 50 Hz. Mach-E best at +1 sample (20 ms), F-150 at +2 samples (40 ms). Tiny win.

## Attribution (sequential waterfall scheme)

Each level's contribution = `RMS_prev − RMS_this`, expressed both in absolute deg/s and as % of the original baseline error. Order matters: I added knobs in roughly decreasing prior-expected impact.

| Step | RMS (deg/s) | Δ (deg/s) | % of baseline error closed |
| --- | ---: | ---: | ---: |
| V0 baseline KS | 1.0336 | — | — |
| V1 + per-seg δ-bias | 0.9075 | +0.1261 | **12.2 %** |
| V2 + per-platform `i_s` rescale | 0.7959 | +0.1116 | **10.8 %** |
| V3 + understeer `K_us` | 0.7433 | +0.0526 | **5.1 %** |
| V4 + per-platform yaw lag | 0.7401 | +0.0032 | **0.3 %** |
| **Total** | | **+0.2935** | **28.4 %** |

By construction the deltas sum to the total. Per-segment bias (V1) and per-platform steering-ratio correction (V2) are roughly equal in impact and together carry 23 of the 28 points; understeer adds another 5; lag is negligible.

## Surprises

- The CSV column `a_lat_meas_mps2` for two F-150 segments is broken (RMS > 100 m/s² — DBC scale or stale-CAN bug). It made the *a_y* residual unusable as a headline metric (combined RMS 7.1 m/s², dominated by those two segments). I switched the primary metric to *yaw rate*, which is clean.
- The two Ford platforms' best `k` go in opposite directions (1.073 vs 0.872) even though their `carParams` steering ratios are nearly identical (17.0 vs 16.9). One per-platform scalar is doing more work than the openpilot-canonical value.
- The V3 understeer coefficients are almost identical across the two very different vehicles (sedan-ish EV vs heavy EV pickup), `K_us ≈ 0.0011 s²/m` — suggesting the missing physics is the same "mild understeer below the limit" everywhere, not a vehicle-specific tyre issue.
- Time lag is essentially zero (1–2 samples). The KS model isn't suffering from steering→yaw transport delay at 50 Hz; the residual is dominated by gain/bias and (slightly) nonlinear yaw gain at speed.

## Limitations

- I evaluated only on the Ford corpus because Tesla CSVs lack a measured yaw-rate channel.
- V1 (per-segment bias) is fit on the same data it's evaluated on. In production you'd estimate `b` from the first ~30 s of each drive — the holdout-style check would be per-segment temporal split, not per-corpus segment split. I did do a 70/30 segment-level holdout for V2 and V3 (the per-platform fits), and both generalise.
- I didn't touch the integrator (RK4 at the input rate is fine here), and I didn't implement an actual ST (dynamic single-track) model with cornering stiffnesses — V3's `K_us` is the linear-bicycle steady-state approximation, which captures most of what ST would buy at the residual-RMS level.
- I assumed yaw-rate is the right primary metric. Path-error and heading-error would be better workshop metrics but require integrating over time (more numerically sensitive). The model's yaw rate `psi_dot` is the prediction; the upstream change in `K_us` would propagate to path predictions trivially.
- Outputs: `out/ladder_results.json`, `out/holdout_results.json`, scripts at `tools/baseline.py`, `tools/ladder.py`, `tools/holdout.py`.

No harness friction encountered (no Write blocks tripped).

```
ISOLATION_REPORT:
read_outside_allowed: []
attempted_blocked: []
shared_dir_writes: []
notes: "Yaw-rate-only metric chosen because two F-150 sim CSVs have broken a_lat decoding (>100 m/s^2 RMS); did not investigate the DBC bug, just routed around it."
```

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "agent-07",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-07/REPORT.md",
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
- `comparable_to_canonical` — for idea-01, "canonical" means a *measured* yaw-rate truth channel on Ford. Agent-01-style fabricated proxies on Tesla → FALSE.
- `attribution_breakdown` — pick one scheme per agent; the agent's primary scheme if multiple are reported (sequential takes precedence over Shapley when both are present and the agent narrates the sequential one). Use the agent's own variant names verbatim — do not rename or normalise across agents.

Notes on `honesty_flags`:
- `named_data_gap_or_missing_truth_channel`: TRUE if the agent explicitly says they could not access a needed source, or that a truth channel is missing for some platform.
- `fabricated_truth_or_proxy_undeclared`: TRUE **only** if the agent substituted a derived/fabricated signal for ground truth **without flagging that substitution** as a limitation. If they flagged it, set FALSE — fabrication that is declared honestly is not dishonest.

Return strict JSON only. The aggregator will parse `stdout` as JSON; any prose breaks the pipeline.
