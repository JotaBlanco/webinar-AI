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

- agent_id: **angleA-m2-agent-02**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-2/agent-02/REPORT.md`

```markdown
# Module-2 / agent-02 — Lateral fidelity report

**Platform scored:** `FORD_MUSTANG_MACH_E_MK1`. The `yaw_rate_meas_rads` and `a_lat_meas_mps2` columns are **measured truth** decoded from rlog CAN, not predictions or self-consistency.

**Speed-known contract honoured.** `v_mps` and `delta_road_rad` are **clamped** inputs; the KS state's own `v`/`δ` updates are overwritten each step. The **predicted** channel under test is `yaw_rate_pred_rads` (V0–V2) or a linear-single-track replacement (V3) consuming the same measured `v, δ`.

**Segment set:** First 120 Mach-E segments (sorted), 348 060 samples at 50 Hz (~116 min driving). Same segment-set and same regime mask across every row.

**Regime definition (held constant):**
- *straight* — `|ψ̇_meas (5-sample boxcar)| < 0.05 rad/s` (313 064 samples)
- *cornering_transient* — not straight ∧ `|dψ̇_meas/dt| > 0.20 rad/s²` (4 241 samples)
- *cornering_steady* — not straight ∧ not transient (30 755 samples)

## Variant ladder (RMSE on `yaw_rate_pred − yaw_rate_meas`, rad/s)

| variant       | RMSE_overall | straight | steady  | transient | marginal Δ overall | total drop vs V0 |
|---------------|-------------:|---------:|--------:|----------:|-------------------:|-----------------:|
| V0_baseline   | 0.01550      | 0.00840  | 0.04020 | 0.05282   | —                  | 0.00000          |
| V1_seg_bias   | 0.01358      | 0.00602  | 0.03711 | 0.04963   | -0.00193           | 0.00193          |
| V2_time_align | 0.01313      | 0.00580  | 0.03691 | 0.04226   | -0.00045           | 0.00237          |
| V3_linear_ST  | 0.01440      | 0.00521  | 0.04129 | 0.05143   | +0.00127 (regression) | 0.00110       |

**Accounting:** sequential / chain decomposition — each row's marginal drop is the overall-RMSE reduction relative to the row above. Sum of signed marginal drops = V0_overall − V3_overall by construction.

**Headline: V0 → V2 cuts overall yaw-rate RMSE from 0.01550 rad/s to 0.01313 rad/s — a 15.3% reduction (24% marginal drop in cornering_transient).**

## What each variant does

- **V0** — `yaw_rate_resid_rads` straight from the CSV, no preprocessing.
- **V1** — per-segment mean-bias subtraction on the residual. Removes IMU yaw-rate offset (~1–3 mrad/s). Explains 81% of the total improvement; biggest gain in *straight* (0.00840 → 0.00602).
- **V2** — best integer-sample lag alignment of `yaw_rate_pred` vs `yaw_rate_meas` per segment, then re-remove bias. Median fitted lag = 3.73 samples ≈ **74 ms** — consistent with rlog timestamp skew between steering-CAN and IMU. Big payoff in *cornering_transient* (14.8% drop).
- **V3** — replace KS with linear single-track steady-state `ψ̇_ST = v·δ / (L + K_us·v²)`, openpilot-canonical `C_αf=286 551, C_αr=355 912 N/rad`, gives `K_us = 1.68e-3 rad/(m/s²)`. **Regressed by 0.00127 rad/s overall.** Physical cause: the openpilot-shipped cornering-stiffness prior is too small (under-correction inversion); on these segments the ST prior over-corrects relative to KS+alignment. Straight regime *did* improve. ST is "directionally right model, wrong calibration" — a real ST upgrade needs a `C_α` fit, not a prior.

## Limitations

- Only AGENTS.md (glossary + truth matrix + operating contract) — no parameter-fit harness. V3 became an honest regression because K_us was wrong for these tyres/segments. A 5-min least-squares fit of `C_α` would likely flip V3 to a strict win.
- Regime thresholds chosen by inspection; not externally validated.
- Per-segment bias estimator uses residual mean — at long one-sided cornering it would absorb signal. Mach-E segments are short (~60 s) so contamination is small but non-zero.

Files: `out/variant_ladder.csv`, `out/meta.json`, `out/analyze.py`.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleA-m2-agent-02",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-2/agent-02/REPORT.md",
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
