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

- agent_id: **angleD-m4-agent-05**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-4/agent-05/REPORT.md`

```markdown
# REPORT — webinar-angle-D / module-4 / agent-05

## Lateral-fidelity ladder on Ford Mustang Mach-E (MK1)

- **Platform.** `FORD_MUSTANG_MACH_E_MK1`. The truth channel `yaw_rate_meas_rads` is **measured** (Ford party DBC, IMU-decoded), not a model output.
- **Contract.** Speed-known, lateral-only. `v` (`v_mps`) and `δ` (`delta_road_rad`) are **clamped** to measured each step (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Speed-state agreement is zero by construction and not a metric.
- **Data.** 8 deterministically-picked Mach-E `sim.csv` segments under `data/sim/segments/FORD_MUSTANG_MACH_E_MK1/`. 23,190 rows total — regime split: straight=22,155, steady-cornering=639, transient-cornering=396. The set is straight-line-dominated; weight that when reading per-regime numbers.
- **Composition.** `regime-segmentation` v0.3 loaded and validated the CSVs and produced the `regime` column; `lateral-fidelity-triage` v0.5 consumed the tagged DataFrame, ran the V0→V4 ladder, and computed per-regime RMSE via `segment.per_regime_rmse`. Both skills share regime thresholds (`|δ|<0.01 rad` straight; `|dδ/dt|<0.05 rad/s` splits steady/transient).
- **Accounting.** Strict marginal, fixed order V0→V1→V2→V3→V4. Each marginal drop is `RMSE(V_{i-1}) − RMSE(V_i)` on the overall residual. Marginals sum to 0.006241; total drop is 0.006241 — well inside the 15% sanity band.
- **Sensor gate.** `python3 skills/lateral-fidelity-triage/sensor.py out/best_V2.csv` → both checks PASS. corr(pred, meas) on cornering = 0.999; RMSE(candidate) = 0.00911 ≤ V0 = 0.01545.

## Variant ladder (RMSE in rad/s; lower is better)

| Variant | Description | Overall | Straight | Steady-corner | Transient-corner | Marginal (overall) |
|---|---|---|---|---|---|---|
| V0 | baseline `yaw_rate_resid_rads` as-is | 0.01545 | 0.01386 | 0.03404 | 0.03688 | — |
| V1 | KS recal `(v/L) tan δ` + per-segment yaw-gyro bias on straights | 0.00932 | 0.00591 | 0.03083 | 0.04004 | **+0.00613** |
| V2 | Linear ST with prior Cα (PARAM_BY_PLATFORM) + per-seg bias | **0.00911** | **0.00292** | 0.03705 | 0.04657 | +0.00021 |
| V3 | Linear ST with fit Cα (L-BFGS-B, bounds 5e4–5e5) + per-seg bias | 0.00921 | 0.00310 | 0.03729 | 0.04680 | **−0.00010 (regression)** |
| V4 | V3 + Ridge residual learner LOO on `[v,|a_y|,|δ|,sign(δ̇)]` | 0.00921 | 0.00318 | 0.03716 | 0.04658 | +0.000006 (noise) |

- **Best variant.** V2 — picked on overall RMSE; written to `out/best_V2.csv`; sensor PASS.
- **V1 owns the win.** 98% of the total V0→V_last drop is V1 alone (recalibrated KS with the canonical `L` from `parameters.py`, plus a per-segment yaw-gyro bias subtracted on straight-line samples). The baseline `yaw_rate_resid_rads` column carries a per-segment DC offset that V1 removes.
- **V2's only contribution is on straights.** Going from KS to linear-ST drops straight RMSE 0.0059 → 0.0029 but worsens cornering (steady 0.0308 → 0.0370). Because straights dominate row count, V2 still wins overall — but anyone who cares about cornering specifically should prefer V1.
- **V3 regression, with a physical reason.** `fit_c_alpha` returned `Cαf = Cαr = 150,000 N/rad` — **exactly the L-BFGS-B initial guess (1.5e5, 1.5e5)**. `pegged_upper=False` per the skill's check, but the optimizer never moved. Cause: with 22,155 of 23,190 rows being straight-line (where the linear-ST gain is `v·δ/L` independent of Cα), the loss surface in the cornering window doesn't dominate. The "fit" is degenerate. V3 ≈ V2 with a hair more noise from re-running `per_segment_bias` on identical predictions; report as regression per v0.5 rule.
- **V4 ships as no-op.** Ridge LOO on top of V3 moved overall RMSE by 6e-6 rad/s — within numerical noise. Per skill rule "if V4 doesn't beat V3 out-of-fold, ship V3 and call V4 a regression", V4 is not shippable; we keep V2 as best.

## Per-change attribution

- **KS recal + yaw-gyro bias on straights (V1)** — Δ = 0.00613 rad/s overall (98% of total improvement). Almost entirely on straights (0.01386 → 0.00591); some degradation on transient cornering (0.03688 → 0.04004), because the per-segment DC bias is computed on straights and doesn't capture cornering-only offsets.
- **Linear-ST prior Cα (V2)** — Δ = 0.00021 rad/s overall, but +0.00299 on straights and **regression** on cornering. The understeer gradient `K_us` with prior Cα reduces predicted yaw at high speed, which is right for straights, wrong for the cornering regime in this segment set.
- **Linear-ST fit Cα (V3)** — Δ = −0.00010 (regression). Optimizer never left `x0`. Fit is unidentifiable on a straight-dominated set.
- **Ridge LOO residual learner (V4)** — Δ = +6e-6 (noise). Features `[v,|a_y|,|δ|,sign(δ̇)]` do not generalise across segments at this signal level.

## Components present / absent

- Present: AGENTS.md (thin); `skills/lateral-fidelity-triage/SKILL.md` v0.5 with `triage.py` and `sensor.py`; `skills/regime-segmentation/SKILL.md` v0.3 with `segment.py`; `tools/run_ladder.py` composition harness.
- Absent: no `evals/`, no held-out test segment set, no plotting/visualisation skill, no reference of measured `a_lat_meas_mps2` as a secondary metric (only `yaw_rate_meas_rads` exercised).

## Limitations and isolation

- Read only the agent-05 module, `code/` symlink, and `data/` symlink. Did not consult sibling agents, other angles, `_shared`, `_launch`, F1, or `raw-model/`.
- Segment selection was deterministic (first 8 sorted Mach-E `sim.csv` paths). No held-out generalisation check beyond V4's per-segment LOO.
- The cornering subset is small (1,035 rows out of 23,190). Per-regime RMSE on steady/transient is statistically thin; treat the 4th-decimal differences with caution.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleD-m4-agent-05",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-4/agent-05/REPORT.md",
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
