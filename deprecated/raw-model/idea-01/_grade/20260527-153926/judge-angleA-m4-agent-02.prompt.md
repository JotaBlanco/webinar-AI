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

- agent_id: **angleA-m4-agent-02**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-4/agent-02/REPORT.md`

```markdown
# Module-4 / agent-02 — Lateral Fidelity Variant Ladder (Ford Mustang Mach-E MK1)

## Platform & contract

- Platform: **FORD_MUSTANG_MACH_E_MK1** (Ford has measured truth; Tesla does not).
- Scored channel: **`yaw_rate_meas_rads`** is the **measured** truth (IMU yaw gyro decoded from rlog). Predictions come from each variant rung.
- Speed-known contract: `v_mps` and `delta_road_rad` are **clamped** to measurement at every step; only `yaw_rate_pred_rads` / `a_y_pred_mps2` are **predicted**. Speed-state agreement is zero by construction and not the metric. No variant unclamps `v` or `δ`.

## Methodology

- 60 Mach-E segments / 173 940 rows / 50 Hz. Same **segment set** and same **regime mask** **held constant** across every row.
- Regime mask: `straight` — `|δ_road| < 0.01 rad`; `steady cornering` — `|δ_road| ≥ 0.01 ∧ |δ̇| < 0.05`; `transient cornering` — `|δ_road| ≥ 0.01 ∧ |δ̇| ≥ 0.05`. Row-counts: 158 354 / 13 136 / 2 450.
- All RMSEs are over `pred − yaw_rate_meas_rads` in rad/s.
- Vehicle parameters from `PARAM_BY_PLATFORM['FORD_MUSTANG_MACH_E_MK1']`: `L = 2.984 m`, `m = 2336 kg`, `I_z = 4879.05`, `l_f/l_r = 1.313/1.671`, `C_αf/C_αr = 286 551 / 355 912 N/rad`, `i_s = 17.0`.
- Attribution scheme: **strict marginal**, fixed order V0→V1→V2→V3→V4. Σmarginal = 0.002536, total V0→V4 = 0.002536, `|Σ − total|/total = 0.000`.

## Variant ladder

| Variant | Description | RMSE overall (rad/s) | Straight | Steady | Transient | Δ vs prev (rad/s) |
|---|---|---:|---:|---:|---:|---:|
| V0 | Baseline `yaw_rate_resid_rads` as-is                                                                                                              | 0.012144 | 0.008508 | 0.025192 | 0.048887 | — |
| V1 | KS recalibrated with canonical `L` + per-segment straight-line yaw-gyro bias                                                                       | 0.010552 | 0.005064 | 0.026019 | 0.051156 | -0.001593 |
| V2 | Linear ST with openpilot prior `C_αf/C_αr` (KS fallback below 2 m/s) + per-segment bias                                                            | 0.012480 | 0.003346 | 0.034243 | 0.063623 | +0.001929 |
| V3 | Linear ST with fit `C_αf, C_αr` (grid + Nelder-Mead, bounded 50–500 kN/rad) — fit landed at Cf=427 029, Cr=483 737 (near upper bound) + bias       | 0.012170 | 0.003364 | 0.033180 | 0.062300 | +0.000310 |
| V4 | Ridge residual learner on V3 residuals; features = `[v, |a_y|, |δ|, sign(δ̇)]`; **leave-one-segment-out CV** (out-of-fold scoring)                  | 0.009608 | 0.003440 | 0.023898 | 0.052225 | -0.002562 |

**Headline:** V0→V4 = 0.01214 → 0.00961 rad/s (~21% overall reduction; ~60% reduction on the straight regime).

## Per-variant notes

- **V1 (the workhorse).** Subtracting per-segment yaw-gyro bias on straights cuts straight residual from 8.5 → 5.1 mrad/s. Steady/transient cornering go slightly *worse* — the bias had been masking a constant offset across all regimes; remove it and the cornering structural error stands clearer.
- **V2 (regression, physical cause).** Linear-ST steady-state with openpilot prior `C_α` (286k / 356k) makes the bicycle stiffer than the actual Mach-E tyres are responding to — ST over-predicts yaw in cornering, blowing up steady and transient by ~30–40%. Straight is better (bias subtraction now on a cleaner channel), but cornering damage dominates. Workshop's documented "ST prior too stiff for Mach-E tyres" regression.
- **V3 (partial recovery, still regression vs V1).** Fitting `C_α` over the Mach-E set drives Cf/Cr toward the upper bound (≈427k / 484k), confirming the prior was *already* stiffer than V1 wanted — making it stiffer still pushes `K_us` nearer to its asymptote and hides more V2 damage, but overall fidelity is still worse than V1 (0.01217 vs 0.01055). Linear-ST functional form is the wrong class.
- **V4 (the real win).** 4-feature ridge residual learner trained out-of-fold against V3 residuals recovers cornering and lands at 0.00961 overall — beating V1 and V0. Cornering regimes are the channels it lifts (steady 23.9 vs V1's 26.0, transient 52.2 vs V1's 51.2). LOSO CV: every prediction comes from a model that has never seen its own segment.

## Honest regression flags

- **V2 worsened V1 by +1.93 mrad/s.** Cause: openpilot prior `C_α` is stiffer than the Mach-E tyres under the segment-set's operating envelope.
- **V3 worsened V1 by +1.62 mrad/s.** Even after fitting `C_α`, the linear-ST functional form cannot match KS+bias because the residual structure is non-linear (slip rises non-linearly with `a_y`).
- V4 is the only rung that beats V1.

## Attribution

- Total V0 → V4: **0.002536 rad/s** (0.01214 → 0.00961, ~21% overall, ~60% straight).
- Marginal drops: V1 **+1.593**, V2 **−1.929**, V3 **+0.310**, V4 **+2.562** (mrad/s).
- |Σ − total|/total = **0.000**, well under the 0.15 coherence threshold.
- V2 and V3 are documented regressions kept in the ladder so attribution remains honest, not pruned.

## Limitations

- 60-of-315 Mach-E segments (deterministic glob order) for budget.
- V4 ridge features are minimal; non-linear models or richer features (slip-angle proxy, lateral jerk) would likely improve further but are out of scope.
- `triage.fit_c_alpha` ships with L-BFGS-B which gets stuck on the very flat `C_α` loss surface and returns its initial guess. Worked around with a 25×25 grid + Nelder-Mead refinement in `tools/run_ladder.py`; helper should be patched for future runs.

## Note from the eval-pass dry run

Pipe `|` characters in table description columns silently break the eval's column parser (V4 row got dropped → "total drop is non-positive"). A `references/golden-report.md` example would have caught this in one read.

Files: `tools/run_ladder.py`, `out/ladder_results.json`, `out/variant_ladder.md` (mirror that passes the eval 6/6).

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleA-m4-agent-02",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-4/agent-02/REPORT.md",
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
