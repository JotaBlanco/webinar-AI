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

- agent_id: **raw-agent-05**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-05/REPORT.md`

```markdown
# Lateral prediction improvements — agent-05

## 1. Headline number

**Primary metric:** pooled RMSE of predicted yaw rate vs. measured yaw rate, across all 545 Ford segments (Mach-E + F-150 Lightning, ~1.58 M samples). Ford is the only platform with a measured truth channel (`Yaw_Data_FD1.VehYaw_W_Actl`); Tesla rlogs have no decoded IMU, so they are excluded from scoring.

| | Yaw-rate RMSE (rad/s) |
|---|---|
| Baseline (as-shipped KS column) | **0.01804** |
| Final (full ladder)             | **0.01466** |
| **Improvement**                 | **−18.7 %** |

Lateral-acceleration RMSE was tracked as a secondary metric; it is dominated by F-150 sensor garbage at startup (a_lat = 1057 m/s² in two segments), so I treat it as a data-quality observation rather than a model headline.

## 2. What I implemented (the ladder)

The model is KS: `ψ̇ = (v/L)·tan(δ_road)`, fed `v_meas` and `δ_meas = δ_wheel / i_s` from CAN. Each step is one targeted modification, then re-scored on the same pooled mask:

- **v0** as-shipped baseline — uses the `yaw_rate_pred_rads` column already written by `generate_simdata_ford.py`.
- **v1** sensor-sanity outlier mask: drop frames with `|a_lat_meas| ≥ 15 m/s²` (catches two stuck-sensor F-150 segments where a_lat hits ~1057 m/s²; 109 of ~1.58 M samples).
- **v2** per-platform static road-wheel offset, fitted by velocity-weighted LS against the baseline residual (Mach-E −0.00012 rad ≈ −0.12° at the wheel; F-150 −0.00060 rad ≈ −0.59°).
- **v3** swap pure-kinematic for steady-state linear bicycle: `ψ̇ = v·δ / (L + K·v²)` with `K_us = m(l_r·C_αr − l_f·C_αf)/(L·C_αf·C_αr)` computed from the canonical openpilot Caf/Car/mass.
- **v4** refit `K_us` per platform jointly from data: Mach-E 0.00073, F-150 0.00282 (canonical was 0.00168 for both).
- **v5** global per-platform time shift between steering input and yaw-rate measurement, picked by per-segment cross-correlation, taken as the median: Mach-E 80 ms, F-150 60 ms.
- **v6** per-segment static steering offset (mean −0.00044 rad, std 0.00131 rad — a real σ ≈ 1.3 mrad per-segment of zero-point drift).

## 3. Attribution

**Scheme: sequential / cumulative.** Each row shows the RMSE *after* applying that change on top of all previous changes. % is delta as fraction of v0 RMSE.

| Step | RMSE | Δ (rad/s) | Δ % of v0 |
|---|---:|---:|---:|
| v0 baseline                                       | 0.01804 |          | — |
| v1  + outlier mask                                | 0.01804 | −0.00000 | −0.00 % |
| v2  + global steering offset                      | 0.01792 | −0.00012 | −0.67 % |
| v3  + steady-state understeer (canonical Caf/Car) | 0.01628 | −0.00164 | −9.09 % |
| v4  + understeer-K refit from data                | 0.01578 | −0.00050 | −2.76 % |
| v5  + global time-shift                           | 0.01557 | −0.00021 | −1.18 % |
| v6  + per-segment offset                          | 0.01466 | −0.00091 | −5.04 % |
| **Total**                                         |         | −0.00338 | **−18.74 %** |

**Marginal effect (each change applied *alone* on top of v1):**

| Change | RMSE | vs v1 |
|---|---:|---:|
| offset only (global)               | 0.01792 | −0.67 % |
| understeer only (canonical prior)  | 0.01641 | −9.03 % |
| understeer-K refit only            | 0.01591 | −11.80 % |

Reading: the single biggest gain is **adding the missing physics** (kinematic → linear-bicycle steady-state, ≈ 9 %). Fitting `K` from data adds another ≈ 3 %. Time alignment and per-segment offsets together pick up another ~6 %, suggesting non-trivial per-recording steering zero drift.

## 4. Surprises

- The canonical openpilot `K_us` for the F-150 (0.00168) is **40 % too low** versus what the data wants (0.00282) — the truck is more understeery than its Caf/Car suggest. Mach-E goes the other way: data wants 0.00073 vs the canonical 0.00168 — i.e. Mach-E is stiffer/less understeery than its openpilot stiffnesses imply. Both numbers are openpilot-canonical per `parameters.py` comments, so this is real signal.
- The lateral-G RMSE on F-150 (10.9 m/s²) is almost entirely two segments where the brake-system sensor latches at +1057 m/s². Pure data-quality issue; the model is fine. Worth flagging upstream.
- Per-segment steering offset has σ ≈ 1.3 mrad (5–95 % spread: −2.4 to +1.9 mrad). That's tens of milli-Nm at the rack — i.e. real device-to-device steering-encoder zero drift, not a one-time platform constant.
- A consistent 60–80 ms positive lag from steering input → measured yaw rate. Plausible as ABS-module CAN publish cadence + filtering on `Yaw_Data_FD1`. Modest contribution to RMSE (~1 %), but the consistency across hundreds of segments suggests it is structural, not noise.

## 5. Limitations

- **Tesla excluded.** Tesla rlogs have no decoded yaw-rate truth channel; only Ford could be scored. Whatever I report is Ford-only.
- **Single metric.** I scored on pooled yaw-rate RMSE. I did not split high-speed/low-speed or by manoeuvre intensity; the ~9 % "understeer adds physics" gain is likely much larger in high-lat-G corners and zero at parking-lot speeds.
- **No held-out evaluation.** v4 `K` fits and v6 per-segment offsets are both fit on the same data they score on. v6 in particular is one DOF per segment — almost guaranteed to flatter itself. A held-out split would shrink v6's contribution; I would expect 2–4 % of the 5 % to survive.
- **No proper ST model.** I used the *steady-state* bicycle (algebraic, instantaneous). A real ST integrator (`β̇`, `ψ̈` as states with transient response) was on the ladder but not built in time. It would primarily help fast-transient corners where steady-state is wrong; my hunch is another 2–5 %.
- **No access to** any cross-angle modulo solutions, sibling agents, or webinar-00 challenge metadata — by design. No PreToolUse blocks tripped.
- **`Write` restriction not hit.** I did not attempt any `report|summary|analysis*.md` write — the harness friction did not bite. All scripts are under `tools/`, all numeric output under `out/ladder_run1.txt` and `out/ladder2_run.txt`.

Artifacts:
- `tools/baseline.py`, `tools/ladder.py`, `tools/ladder2.py`
- `out/ladder_run1.txt`, `out/ladder2_run.txt`

```
ISOLATION_REPORT:
read_outside_allowed: []
attempted_blocked: []
shared_dir_writes: []
notes: "Stayed within ./code (read-only), ./data (read-only), and agent-05/ for all writes. No sibling/cross-angle/webinar-00 access attempted."
```

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "raw-agent-05",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-05/REPORT.md",
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
